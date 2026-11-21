"""Action agent: writes supplier mails, sends them and reads the replies.

A mail that orders, accepts or promises needs a click by a person. Only
questions go out alone, as the pack allows in `auto_approve`. The address
always comes from the master data, never from an LLM text or a document
(docs/import-und-routen.md §6).
"""

import datetime
import email.message
import email.utils
import hashlib
import logging
import pathlib
import re
from typing import Any

import pydantic

from lineguard import clock
from lineguard import db
from lineguard import llm as llm_module
from lineguard import models
from lineguard import runtime
from lineguard.connectors import mail as mail_module

logger = logging.getLogger(__name__)
_PROMPTS = pathlib.Path(__file__).resolve().parent.parent / "prompts"
_ATTACHMENT_TYPES = (".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".txt", ".csv")
_DONE_STATUS = ("sent", "dry_run")
_LANGUAGES = {
    "en": "English", "de": "German", "pl": "Polish", "ko": "Korean",
    "zh": "Chinese (Simplified)", "fr": "French", "es": "Spanish",
    "it": "Italian", "ja": "Japanese",
}
_PURPOSE_TEXT = {
    "order": "We accept your offer and order the goods listed below. Please confirm the quantity and the arrival time.",
    "pickup": "The goods listed below are ready and not received yet. Please arrange the release and the delivery to our site, and confirm the arrival time.",
    "sort": "A lot failed our incoming inspection. We sort the lot and use the good parts. Please support the sorting and send your corrective action report.",
    "status_request": "Please confirm the current status, the quantity and the arrival time of the goods listed below.",
    "follow_up": "We did not get a reply to our last mail. Please answer today.",
}


def mailer(rt: runtime.Runtime) -> mail_module.Mailer:
    return rt.mailer or mail_module.from_pack(
        rt.pack.mail.sender_env, rt.pack.mail.sender_name, rt.ws)


def _facts_for_mail(rt: runtime.Runtime, option: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    data = db.loads(option.get("data"), {})
    component = db.one(
        rt.conn, rt.ws,
        "SELECT * FROM components WHERE workspace_id = ? AND component_id = ?",
        (case["component_id"],)) or {}
    return {
        "part": case["component_id"], "part_description": component.get("description"),
        "released_revision": component.get("released_rev"),
        "quantity": option["qty_gain"], "po_number": data.get("po_number") or case.get("po_number"),
        "wanted": "earlier arrival" if data.get("asks_earlier") else None,
        "cost_eur": option["cost_eur"] or None,
        "arrival_needed_before": db.loads(case.get("detail"), {}).get("latest_useful_arrival"),
        "delivery_site": rt.pack.site, "due_date": case.get("due_at"),
        "offer_valid_until": option.get("valid_until"),
    }


def _template(purpose: str, facts: dict[str, Any], sender: str, hours: float) -> models.EmailDraftOut:
    """Fixed English text for when the LLM is not available."""
    lines = [f"- {key.replace('_', ' ')}: {value}" for key, value in facts.items()
             if value not in (None, "")]
    body = "\n".join([
        "Dear Sir or Madam,", "", _PURPOSE_TEXT[purpose], "", *lines, "",
        f"Please reply within {hours:g} hours. The goods are needed for a fixed delivery date.",
        "", "Best regards,", sender])
    return models.EmailDraftOut(
        subject=f"{purpose.replace('_', ' ').capitalize()}: {facts.get('part') or ''}",
        body=body, language="en", commits_money=purpose == "order")


def write_draft(rt: runtime.Runtime, purpose: str, option: dict[str, Any], case: dict[str, Any], contact: dict[str, Any]) -> models.EmailDraftOut:
    """Writes the mail with the LLM, or with the fixed text as fallback."""
    facts = _facts_for_mail(rt, option, case)
    sender = rt.pack.mail.sender_name
    hours = rt.pack.mail.follow_up_hours
    po = facts.get("po_number")
    prefix = f"{rt.pack.mail.subject_tag}[PO {po}]" if po else rt.pack.mail.subject_tag
    draft = _template(purpose, facts, sender, hours)
    if rt.llm is not None:
        system = ((_PROMPTS / "email_draft.md").read_text(encoding="utf-8")
                  .replace("[LANGUAGE]", _LANGUAGES.get(
                      contact.get("language") or "en", contact.get("language") or "English"))
                  .replace("[REPLY_HOURS]", f"{hours:g}")
                  .replace("[SENDER]", sender).replace("[SUBJECT_PREFIX]", prefix))
        prompt = (f"Purpose: {purpose}\nWhat the mail must say: {_PURPOSE_TEXT[purpose]}\n"
                  f"Supplier: {contact.get('name')}, contact {contact.get('contact_name')}\n"
                  f"Facts: {facts}")
        try:
            draft = models.EmailDraftOut.model_validate(rt.llm.extract(
                rt.conn, rt.ws, purpose="draft_email", system=system, prompt=prompt))
        except (llm_module.LlmError, pydantic.ValidationError) as error:
            logger.warning("Draft falls back to the fixed text: %s", error)
    if not draft.subject.startswith(prefix):
        draft.subject = f"{prefix} {draft.subject}".strip()
    return draft


def _is_routine(rt: runtime.Runtime, purpose: str, option: dict[str, Any], draft: models.EmailDraftOut) -> bool:
    allowed = rt.pack.auto_approve
    return (purpose in allowed.action_kinds and not draft.commits_money
            and (option["cost_eur"] or 0) <= allowed.max_cost_eur)


def handle_requested(rt: runtime.Runtime, event: dict[str, Any]) -> None:
    """Handles `action.requested`: one mail per option, never a second."""
    payload = event["payload"]
    option = db.one(rt.conn, rt.ws,
                    "SELECT * FROM options WHERE workspace_id = ? AND id = ?",
                    (payload["option_id"],))
    if option is None:
        return
    case = db.one(rt.conn, rt.ws,
                  "SELECT * FROM cases WHERE workspace_id = ? AND id = ?",
                  (option["case_id"],))
    purpose = payload.get("purpose") or option["action_kind"] or "status_request"
    key = f"{option['case_id']}:{purpose}:{option['supplier_id']}:{option['id']}"
    if case is None or db.one(
            rt.conn, rt.ws,
            "SELECT id FROM actions WHERE workspace_id = ? AND idempotency_key = ?",
            (key,)):
        return
    contact = db.one(
        rt.conn, rt.ws,
        "SELECT * FROM contacts WHERE workspace_id = ? AND supplier_id = ?",
        (option["supplier_id"],))
    now = clock.iso()
    if contact is None or not contact["email"]:
        db.insert(rt.conn, "actions", rt.ws, case_id=case["id"], option_id=option["id"],
                  type="escalate", kind=purpose, target="no_contact", status="failed",
                  idempotency_key=key, created_at=now,
                  result={"text": "Kein Kontakt in den Stammdaten für diesen Lieferanten"})
        return
    draft = write_draft(rt, purpose, option, case, contact)
    routine = _is_routine(rt, purpose, option, draft)
    action_id = db.insert(
        rt.conn, "actions", rt.ws, case_id=case["id"], option_id=option["id"],
        decision_id=option["decision_id"], type="email", kind=purpose,
        target=option["supplier_id"],
        status="approved" if routine else "awaiting_approval",
        idempotency_key=key, created_at=now)
    email_id = db.insert(
        rt.conn, "emails", rt.ws, action_id=action_id, case_id=case["id"],
        direction="out", from_addr=mailer(rt).address, to_addr=contact["email"],
        subject=draft.subject, body=draft.body,
        language=contact["language"] or draft.language,
        po_ref=db.loads(option["data"], {}).get("po_number"),
        status="approved" if routine else "draft", routine=routine,
        commits_money=draft.commits_money or purpose == "order",
        reason=option["title"], created_at=now)
    db.update(rt.conn, "options", rt.ws, option["id"], action_id=action_id)
    db.emit(rt.conn, rt.ws, "email.drafted", {"email_id": email_id}, priority=3,
            dedupe_key=f"email.drafted:{email_id}")
    if routine or payload.get("approved_by"):
        send(rt, email_id, payload.get("approved_by") or "auto_approve")


def send(rt: runtime.Runtime, email_id: int, approved_by: str, subject: str | None = None, body: str | None = None) -> dict[str, Any]:
    """Sends one mail once. A second call for the same mail does nothing."""
    row = db.one(rt.conn, rt.ws,
                 "SELECT * FROM emails WHERE workspace_id = ? AND id = ?", (email_id,))
    if row is None:
        raise KeyError(email_id)
    if row["status"] in _DONE_STATUS or row["direction"] != "out":
        return row
    client = mailer(rt)
    # The Message-ID is stored before the send, so a crash cannot cause a
    # second mail with another id.
    message_id = row["message_id"] or client.new_message_id()
    db.update(rt.conn, "emails", rt.ws, email_id, message_id=message_id,
              subject=subject or row["subject"], body=body or row["body"],
              status="approved", approved_by=approved_by)
    try:
        status = client.send(row["to_addr"], subject or row["subject"],
                             body or row["body"], message_id, row["in_reply_to"])
    except mail_module.MailError as error:
        db.update(rt.conn, "emails", rt.ws, email_id, status="failed", reason=str(error))
        raise
    now = clock.iso()
    db.update(rt.conn, "emails", rt.ws, email_id, status=status, sent_at=now)
    if row["action_id"]:
        db.update(rt.conn, "actions", rt.ws, row["action_id"], status="done")
    if row["case_id"]:
        rt.conn.execute(
            "UPDATE cases SET state = 'in_execution', updated_at = ? "
            "WHERE workspace_id = ? AND id = ? AND state IN ('approved')",
            (now, rt.ws, row["case_id"]))
    db.emit(rt.conn, rt.ws, "email.sent", {"email_id": email_id}, priority=3,
            dedupe_key=f"email.sent:{email_id}")
    return db.one(rt.conn, rt.ws,
                  "SELECT * FROM emails WHERE workspace_id = ? AND id = ?", (email_id,))


# ---------- replies ----------


def _match_thread(rt: runtime.Runtime, message: email.message.EmailMessage) -> dict[str, Any] | None:
    """The sent mail this reply belongs to.

    Order: thread headers, then the order number in the subject, then the
    sender.
    """
    sent = db.rows(
        rt.conn, rt.ws,
        "SELECT * FROM emails WHERE workspace_id = ? AND direction = 'out' "
        "AND message_id IS NOT NULL ORDER BY id DESC")
    thread = f"{message.get('In-Reply-To', '')} {message.get('References', '')}"
    for row in sent:
        if row["message_id"] in thread:
            return row
    numbers = re.findall(r"PO\s*(\w+)", str(message.get("Subject", "")))
    for row in sent:
        if row["po_ref"] and row["po_ref"] in numbers:
            return row
    sender = email.utils.parseaddr(str(message.get("From", "")))[1].lower()
    for row in sent:
        if (row["to_addr"] or "").lower() == sender:
            return row
    return None


def _body_text(message: email.message.EmailMessage) -> str:
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    text = part.get_content()
    if part.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    return text.strip()


def _store_file(rt: runtime.Runtime, path: str, data: bytes) -> None:
    sha = hashlib.sha256(data).hexdigest()
    key = f"versions/{sha[:12]}/{path}"
    rt.blob.put(key, data)
    file_id = db.insert(
        rt.conn, "files", rt.ws, path=path, sha256=sha, version=1, bytes=len(data),
        blob_key=key, doc_class="supplier_mail", parser="document", priority=2,
        first_seen_at=clock.iso())
    db.emit(rt.conn, rt.ws, "file.added", {"file_id": file_id, "path": path},
            priority=2, dedupe_key=f"file.added:{path}:{sha}",
            partition_key=f"file:{path}")


def receive(rt: runtime.Runtime, message: email.message.EmailMessage) -> int | None:
    """Stores one incoming mail and gives body and attachments to the reader.

    Returns:
        The id of the stored mail, or None when it was stored before.
    """
    message_id = str(message.get("Message-ID") or "").strip()
    if not message_id or db.one(
            rt.conn, rt.ws,
            "SELECT id FROM emails WHERE workspace_id = ? AND message_id = ?",
            (message_id,)):
        return None
    question = _match_thread(rt, message)
    sender = email.utils.parseaddr(str(message.get("From", "")))[1].lower()
    contact = db.one(
        rt.conn, rt.ws,
        "SELECT * FROM contacts WHERE workspace_id = ? AND LOWER(email) = ?", (sender,))
    supplier = contact["supplier_id"] if contact else "unknown"
    text = _body_text(message)
    email_id = db.insert(
        rt.conn, "emails", rt.ws, case_id=question["case_id"] if question else None,
        action_id=question["action_id"] if question else None, direction="in",
        from_addr=sender, to_addr=mailer(rt).address,
        subject=str(message.get("Subject", "")), body=text[:8000],
        message_id=message_id, in_reply_to=question["message_id"] if question else None,
        po_ref=question["po_ref"] if question else None, status="received",
        created_at=clock.iso())
    asked = (f"--- Our question ---\nSubject: {question['subject']}\n{question['body']}\n\n"
             if question else "")
    folder = f"mail/{supplier}/{email_id}"
    document = (f"{asked}--- Reply from {sender} ({supplier}) ---\n"
                f"Subject: {message.get('Subject', '')}\n{text}")
    _store_file(rt, f"{folder}/body.txt", document.encode("utf-8"))
    for part in message.iter_attachments():
        name = pathlib.PurePosixPath(part.get_filename() or "attachment").name
        if pathlib.PurePosixPath(name).suffix.lower() in _ATTACHMENT_TYPES:
            _store_file(rt, f"{folder}/{name}", part.get_payload(decode=True) or b"")
    db.emit(rt.conn, rt.ws, "email.received", {"email_id": email_id}, priority=3,
            dedupe_key=f"email.received:{email_id}")
    return email_id


def poll_and_follow_up(rt: runtime.Runtime, event: dict[str, Any] | None = None) -> None:
    """Handles the action tick: read the inbox, then chase silent threads."""
    del event
    known = {row["message_id"] for row in db.rows(
        rt.conn, rt.ws,
        "SELECT message_id FROM emails WHERE workspace_id = ? AND message_id IS NOT NULL")}
    senders = [row["email"] for row in db.rows(
        rt.conn, rt.ws, "SELECT email FROM contacts WHERE workspace_id = ?")]
    try:
        for message in mailer(rt).poll(senders, known):
            receive(rt, message)
    except mail_module.MailError as error:
        logger.warning("Inbox not read: %s", error)
    _follow_up(rt)


def _follow_up(rt: runtime.Runtime) -> None:
    """One reminder for a sent question without reply after the wait time.

    Only mails that really went out count. A mail that DRY_RUN only logged
    cannot get an answer.
    """
    limit = clock.now() - datetime.timedelta(hours=rt.pack.mail.follow_up_hours)
    waiting = db.rows(
        rt.conn, rt.ws,
        "SELECT e.* FROM emails e JOIN cases c ON c.id = e.case_id "
        "WHERE e.workspace_id = ? AND e.direction = 'out' AND e.in_reply_to IS NULL "
        "AND e.status = 'sent' AND e.sent_at < ? "
        "AND c.state NOT IN ('closed', 'dismissed') "
        "AND NOT EXISTS (SELECT 1 FROM emails r WHERE r.workspace_id = e.workspace_id "
        "AND r.in_reply_to = e.message_id)", (clock.iso(limit),))
    for row in waiting:
        if "@" not in (row["to_addr"] or ""):
            continue
        email_id = db.insert(
            rt.conn, "emails", rt.ws, action_id=row["action_id"], case_id=row["case_id"],
            direction="out", from_addr=row["from_addr"], to_addr=row["to_addr"],
            subject=f"Re: {row['subject']}",
            body=(f"{_PURPOSE_TEXT['follow_up']}\n\n--- Our mail ---\n{row['body']}"),
            language="en", in_reply_to=row["message_id"], po_ref=row["po_ref"],
            status="approved", routine=1, reason="Nachfrage ohne Antwort",
            created_at=clock.iso())
        send(rt, email_id, "auto_approve")
