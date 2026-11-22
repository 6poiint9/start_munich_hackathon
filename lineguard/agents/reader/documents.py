"""Reads documents, scans and free text into facts with the LLM (wave 2).

Content from outside is data and never an instruction
(docs/import-und-routen.md §6): the prompt says so, a suspicious document
is flagged and counts in no calculation, and an id from the answer counts
only if the master data knows it.
"""

import functools
import logging
import pathlib
import re
from typing import Any

import pydantic

from lineguard import db
from lineguard import llm as llm_module
from lineguard import models
from lineguard import runtime
from lineguard import timeutil
from lineguard.agents.reader import kinds
from lineguard.agents.reader import notify
from lineguard.tools import content

logger = logging.getLogger(__name__)
_PROMPTS = pathlib.Path(__file__).resolve().parent.parent.parent / "prompts"
_MIN_CONFIDENCE = 0.7
_DATE_COLUMNS = ("eta", "valid_until")
_MAX_NOTES = 120


@functools.cache
def _template(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8")


def role_keys(rt: runtime.Runtime) -> list[str]:
    """Role keys of the approval rules and the pack, with titles if known."""
    keys: dict[str, str] = {}

    def add(value: Any) -> None:
        for role in value if isinstance(value, list) else [value]:
            if role:
                keys.setdefault(role, "")
    for rule in rt.pack.approval_policy.get("rules", []):
        for name in ("role", "add_role", "fallback_role", "below", "above"):
            add(rule.get(name))
        for tier in rule.get("tiers", []):
            add(tier.get("role"))
    for role, title in rt.pack.roles.items():
        keys[role] = title
    return [f"{key} ({title})" if title and title != key else key
            for key, title in keys.items()]


def system_prompt(rt: runtime.Runtime) -> str:
    """The reader prompt with the master data of the workspace."""
    components = db.rows(
        rt.conn, rt.ws,
        "SELECT component_id, description, released_rev FROM components "
        "WHERE workspace_id = ? ORDER BY component_id")
    suppliers = db.rows(
        rt.conn, rt.ws,
        "SELECT supplier_id, name, language FROM contacts "
        "WHERE workspace_id = ? ORDER BY supplier_id")
    parts = db.rows(
        rt.conn, rt.ws,
        "SELECT DISTINCT supplier_id, component_id FROM facts "
        "WHERE workspace_id = ? AND fact_type = 'supplier_part' ORDER BY 1, 2")
    aliases = [f"{a['supplier_part']} = {a['component_id']}" for a in rt.pack.aliases]

    def lines(rows: list[dict[str, Any]]) -> str:
        return "\n".join(
            "; ".join(str(v) for v in row.values() if v) for row in rows) or "-"
    supplier_parts = lines(parts)
    if aliases:
        supplier_parts = f"{supplier_parts}\nSupplier part numbers: {', '.join(aliases)}"
    return (_template("reader_extract.md")
            .replace("[DOC_CLASSES]", ", ".join(sorted(rt.pack.source_rank)) or "other")
            .replace("[ROLE_KEYS]", ", ".join(role_keys(rt)) or "-")
            .replace("[COMPONENTS]", lines(components))
            .replace("[SUPPLIERS]", lines(suppliers))
            .replace("[SUPPLIER_PARTS]", supplier_parts))


def _ask(rt: runtime.Runtime, purpose: str, prompt: str, images: list[tuple[bytes, str]], file_id: int | None) -> models.DocumentOut:
    """Calls the LLM and validates. One retry with the error message."""
    system = system_prompt(rt)
    error_text = ""
    for _ in range(2):
        answer = rt.llm.extract(
            rt.conn, rt.ws, purpose=purpose, system=system,
            prompt=prompt + error_text, images=images, file_id=file_id)
        try:
            return models.DocumentOut.model_validate(answer)
        except pydantic.ValidationError as error:
            error_text = (f"\n\nYour last answer was invalid: {error.errors()[:3]}. "
                          "Answer again with valid JSON.")
    raise llm_module.LlmError("The answer did not match the schema twice")


def _path_hints(route: Any, path: str) -> dict[str, str]:
    hints = {}
    for field, pattern in route.path_fields.items():
        match = re.search(pattern, path)
        if match:
            hints[field] = match[1]
    return hints


def read(rt: runtime.Runtime, route: Any, file: dict[str, Any], ctx: kinds.Context) -> bool:
    """Reads one document into facts.

    Returns:
        False when no LLM is configured or the file cannot be read. The
        file then keeps its status ('new' or 'manual').
    """
    if rt.llm is None:
        return False
    hints = _path_hints(route, file["path"])
    is_mail = file["doc_class"] == "supplier_mail"
    if is_mail:
        # Stored by the action agent as mail/<supplier>/<mail id>/<name>.
        hints["supplier_id"] = file["path"].split("/")[1]
    try:
        extracted = content.extract_parts(file["path"], rt.blob.get(file["blob_key"]))
        prefix = (
            f"File path: {file['path']}\n"
            f"Known from the path: {hints or 'nothing'}\n"
            f"Expected facts: {', '.join(route.expect) or 'whatever the document states'}\n\n"
            "Document:\n")
        parts = []
        for location, text, images in extracted:
            parts.extend((location, text[start:start + content.MAX_TEXT_CHARS], [])
                         for start in range(0, len(text), content.MAX_TEXT_CHARS)
                         if text[start:start + content.MAX_TEXT_CHARS].strip())
            parts.extend((location, "(see the image)", [image]) for image in images)
        if not parts:
            raise content.ContentError("Document contains no text or images")
        documents = [
            _ask(rt, "read_document",
                 f"{prefix}{part}\n\nLocation: {location}. Part {index} of {len(parts)}.",
                 part_images, file["id"])
            for index, (location, part, part_images) in enumerate(parts, 1)]
    except (content.ContentError, llm_module.LlmError) as error:
        db.update(rt.conn, "files", rt.ws, file["id"], parse_status="manual",
                  parse_error=str(error))
        logger.warning("Document %s not read: %s", file["path"], error)
        return False
    doc_class = route.doc_class
    if is_mail:
        # A mail keeps the rank of a mail, whatever it says about itself.
        doc_class = "supplier_mail"
    elif documents[0].doc_class in rt.pack.source_rank:
        doc_class = documents[0].doc_class
    ctx.rank = rt.pack.rank_of(doc_class)
    rt.conn.execute("BEGIN IMMEDIATE")
    try:
        db.update(rt.conn, "files", rt.ws, file["id"], doc_class=doc_class)
        suspicious = next((doc for doc in documents if doc.suspicious), None)
        for index, (document, (location, _, part_images)) in enumerate(zip(documents, parts, strict=True), 1):
            if suspicious:
                document = document.model_copy(update={
                    "suspicious": True,
                    "suspicious_reason": suspicious.suspicious_reason})
            for fact in document.facts:
                fact.locator = f"{location}, part {index}: {fact.locator or 'document'}"
            store(rt, ctx, document, "vision" if part_images else "llm", hints,
                  trusted_types=frozenset(route.expect))
    except Exception:
        rt.conn.execute("ROLLBACK")
        raise
    rt.conn.execute("COMMIT")
    return True


# Fact types that give a person power. They count only from a file whose
# route names them in `expect`, never from any other document or mail.
_PRIVILEGED_TYPES = frozenset({"person_role"})


def store(rt: runtime.Runtime, ctx: kinds.Context, document: models.DocumentOut, extracted_by: str, hints: dict[str, str] | None = None, trusted_types: frozenset[str] = frozenset()) -> int:
    """Stores the validated facts of one document. Returns their count."""
    hints = hints or {}
    known_roles = {key.split(" (")[0] for key in role_keys(rt)}
    known_components = {
        r["component_id"] for r in db.rows(
            rt.conn, rt.ws,
            "SELECT component_id FROM components WHERE workspace_id = ?")}
    known_suppliers = {
        r["supplier_id"] for r in db.rows(
            rt.conn, rt.ws,
            "SELECT supplier_id FROM contacts WHERE workspace_id = ?")}
    alias = {a["supplier_part"]: a["component_id"] for a in rt.pack.aliases}
    if document.suspicious:
        ctx.fact("info", 0, value_text=document.suspicious_reason or document.summary,
                 suspicious=1, suspicious_reason=document.suspicious_reason,
                 source_locator="document", extracted_by=extracted_by,
                 supplier_id=hints.get("supplier_id"),
                 data={"summary": document.summary})
    for number, fact in enumerate(document.facts, 1):
        if fact.fact_type in _PRIVILEGED_TYPES:
            if fact.fact_type not in trusted_types or fact.value_text not in known_roles:
                continue
        component = fact.component_id
        if component not in known_components:
            component = alias.get(fact.supplier_part or "") or alias.get(component or "")
        supplier = hints.get("supplier_id")
        if not supplier and fact.supplier_id in known_suppliers:
            supplier = fact.supplier_id
        columns = fact.model_dump(exclude={
            "fact_type", "component_id", "supplier_part", "supplier_id",
            "locator", "confidence", "data", "po_number"})
        for name in _DATE_COLUMNS:
            columns[name] = timeutil.normalize(columns.get(name))
        data = dict(fact.data)
        if fact.supplier_part:
            data["supplier_part"] = fact.supplier_part
        if fact.component_id and component is None:
            data["unmatched_component"] = fact.component_id
        ctx.fact(
            fact.fact_type, number, component_id=component, supplier_id=supplier,
            po_number=fact.po_number or hints.get("po_number"),
            doc_date=timeutil.normalize(document.doc_date),
            source_locator=fact.locator or "document",
            confidence=fact.confidence, extracted_by=extracted_by,
            suspicious=int(document.suspicious),
            needs_review=int(fact.confidence < _MIN_CONFIDENCE),
            data=data, **columns)
    return len(document.facts)


def read_notes(rt: runtime.Runtime, event: dict[str, Any]) -> None:
    """Reads the free text of one table file in batches."""
    if rt.llm is None:
        return
    file = db.one(rt.conn, rt.ws,
                  "SELECT * FROM files WHERE workspace_id = ? AND id = ?",
                  (event["payload"]["file_id"],))
    if file is None or not file["is_current"]:
        return
    notes = db.rows(
        rt.conn, rt.ws,
        "SELECT * FROM facts WHERE workspace_id = ? AND fact_type = 'note' "
        "AND source_file_id = ? AND superseded_by IS NULL ORDER BY id",
        (file["id"],))
    if not notes:
        return
    try:
        documents = []
        for start in range(0, len(notes), _MAX_NOTES):
            listed = "\n".join(
                f"- [{n['source_locator']}] part={n['component_id'] or '-'} "
                f"supplier={n['supplier_id'] or '-'} po={n['po_number'] or '-'} "
                f"ref={n['ref'] or '-'}: {n['value_text']}"
                for n in notes[start:start + _MAX_NOTES])
            prompt = (
                f"File path: {file['path']}\n"
                "These are remarks from the rows of a table. Each line names the row "
                "and the ids of that row. Extract facts only from remarks that change "
                "stock, quantities, dates, revisions or supply. Skip the others. Copy "
                "the ids of the row into the fact and use the row as locator.\n\n"
                f"{listed}")
            documents.append(_ask(rt, "read_notes", prompt, [], file["id"]))
    except llm_module.LlmError as error:
        logger.warning("Notes of %s not read: %s", file["path"], error)
        return
    route = rt.pack.route_for(file["path"])
    ctx = kinds.Context(conn=rt.conn, ws=rt.ws, pack=rt.pack, file=file,
                        rank=rt.pack.rank_of(route.doc_class))
    rt.conn.execute("BEGIN IMMEDIATE")
    try:
        rt.conn.execute(
            "DELETE FROM facts WHERE workspace_id = ? AND source_file_id = ? "
            "AND extracted_by = 'llm_note'", (rt.ws, file["id"]))
        suspicious = next((doc for doc in documents if doc.suspicious), None)
        for document in documents:
            if suspicious:
                document = document.model_copy(update={
                    "suspicious": True,
                    "suspicious_reason": suspicious.suspicious_reason})
            store(rt, ctx, document, "llm_note")
    except Exception:
        rt.conn.execute("ROLLBACK")
        raise
    rt.conn.execute("COMMIT")
    notify.facts_updated(rt, ctx.touched or {"*"})
