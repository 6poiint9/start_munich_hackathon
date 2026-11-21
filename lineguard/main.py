"""HTTP API for the page: state, cases, evidence files and approvals."""

import contextlib
import mimetypes
from typing import Any

import fastapi
from fastapi import responses
from fastapi.middleware import cors

from lineguard import approvals
from lineguard import clock
from lineguard import config
from lineguard import db
from lineguard import pack as pack_module
from lineguard import runtime
from lineguard import views
from lineguard.agents import watcher
from lineguard.connectors import blob as blob_module
from lineguard.connectors import source as source_module
from lineguard.policy import engine


def create_app(pack: pack_module.PackConfig | None = None, lifespan: Any = None, llm: Any = None) -> fastapi.FastAPI:
    """Builds the API for one workspace.

    Each request opens its own database connection. SQLite allows many
    readers next to the one writer of the agents.
    """
    pack = pack or pack_module.load()
    app = fastapi.FastAPI(title="Lineguard", lifespan=lifespan)
    app.add_middleware(
        cors.CORSMiddleware,
        allow_origins=config.get("CORS_ORIGINS", "http://localhost:3000").split(","),
        allow_methods=["*"], allow_headers=["*"])
    app.state.pack = pack

    def open_runtime():
        conn = db.connect(pack.workspace)
        store = blob_module.LocalBlobStore(config.data_dir(pack.workspace))
        with contextlib.closing(conn):
            yield runtime.Runtime(conn=conn, pack=pack, blob=store, llm=llm)

    app.state.open_runtime = open_runtime
    runtime_dependency = fastapi.Depends(open_runtime)

    @app.get("/healthz")
    def healthz(rt: runtime.Runtime = runtime_dependency) -> dict[str, Any]:
        failed = db.one(
            rt.conn, rt.ws,
            "SELECT COUNT(*) AS n FROM events WHERE workspace_id = ? "
            "AND status = 'failed'") or {}
        oldest = db.one(
            rt.conn, rt.ws,
            "SELECT MIN(created_at) AS t FROM events WHERE workspace_id = ? "
            "AND status = 'pending'") or {}
        lag = 0.0
        if oldest.get("t"):
            lag = (clock.now() - clock.parse(oldest["t"])).total_seconds()
        calls = db.one(
            rt.conn, rt.ws,
            "SELECT COUNT(*) AS n, SUM(cache_hit) AS hits, "
            "SUM(tokens_in) AS tokens_in, SUM(tokens_out) AS tokens_out "
            "FROM llm_calls WHERE workspace_id = ?") or {}
        return {"status": "ok", "workspace": rt.ws,
                "failed_events": failed.get("n") or 0,
                "queue_lag_seconds": max(lag, 0.0), "llm_calls": calls}

    @app.get("/state")
    def get_state(at: str | None = None, rt: runtime.Runtime = runtime_dependency) -> dict[str, Any]:
        moment = clock.parse(at) if at else None
        return views.state(rt, moment)

    @app.get("/cases/{case_id}")
    def get_case(case_id: int, rt: runtime.Runtime = runtime_dependency) -> dict[str, Any]:
        found = views.case(rt, case_id)
        if found is None:
            raise fastapi.HTTPException(404, "Fall nicht gefunden")
        return found

    @app.get("/files/{file_id}/content")
    def get_file(file_id: int, rt: runtime.Runtime = runtime_dependency) -> responses.Response:
        file = db.one(rt.conn, rt.ws,
                      "SELECT * FROM files WHERE workspace_id = ? AND id = ?",
                      (file_id,))
        if file is None or not rt.blob.exists(file["blob_key"]):
            raise fastapi.HTTPException(404, "Datei nicht gefunden")
        media_type = mimetypes.guess_type(file["path"])[0] or "application/octet-stream"
        return responses.Response(rt.blob.get(file["blob_key"]), media_type=media_type)

    def current_person(rt: runtime.Runtime, request: fastapi.Request, roles: list[str] | None) -> dict[str, Any]:
        """The person of the request. Checks the role when roles are given."""
        person_id = request.headers.get("X-Lineguard-User")
        if not person_id:
            raise fastapi.HTTPException(401, "Header X-Lineguard-User fehlt")
        if roles is None:
            known = engine.persons(rt).get(person_id)
            if known is None:
                raise fastapi.HTTPException(403, "Person ist nicht bekannt")
            return known
        try:
            return engine.require_role(rt, person_id, roles)
        except engine.NotAllowedError as error:
            raise fastapi.HTTPException(403, str(error)) from error

    def reason_of(body: dict[str, Any] | None) -> str:
        reason = str((body or {}).get("reason") or "").strip()
        if not reason:
            raise fastapi.HTTPException(422, "Ein Grund ist Pflicht")
        return reason

    def run(action: Any, *args: Any) -> dict[str, Any]:
        try:
            return action(*args)
        except KeyError as error:
            raise fastapi.HTTPException(404, "Nicht gefunden") from error
        except approvals.StateError as error:
            raise fastapi.HTTPException(409, str(error)) from error

    @app.get("/events")
    def get_events(limit: int = 50, rt: runtime.Runtime = runtime_dependency) -> list[dict[str, Any]]:
        found = db.rows(
            rt.conn, rt.ws,
            "SELECT id, type, status, priority, created_at, finished_at, "
            "handled_by, payload, error FROM events WHERE workspace_id = ? "
            "AND type != 'tick' ORDER BY id DESC LIMIT ?", (min(limit, 500),))
        for event in found:
            event["payload"] = db.loads(event["payload"], {})
        return found

    @app.post("/sync")
    def post_sync(request: fastapi.Request, rt: runtime.Runtime = runtime_dependency) -> dict[str, Any]:
        current_person(rt, request, None)
        return {"changes": watcher.sync(rt, source_module.from_pack(rt.pack))}

    @app.post("/corrections/{correction_id}/approve")
    def approve_correction(correction_id: int, request: fastapi.Request, rt: runtime.Runtime = runtime_dependency) -> dict[str, Any]:
        person = current_person(rt, request, ["erp_owner"])
        return run(approvals.approve_correction, rt, correction_id, person)

    @app.post("/corrections/{correction_id}/reject")
    def reject_correction(correction_id: int, request: fastapi.Request, body: dict[str, Any] | None = None, rt: runtime.Runtime = runtime_dependency) -> dict[str, Any]:
        person = current_person(rt, request, ["erp_owner"])
        return run(approvals.reject_correction, rt, correction_id, person, reason_of(body))

    @app.post("/corrections/{correction_id}/count")
    def count_correction(correction_id: int, request: fastapi.Request, rt: runtime.Runtime = runtime_dependency) -> dict[str, Any]:
        person = current_person(rt, request, ["erp_owner", "site_lead"])
        return run(approvals.request_count, rt, correction_id, person)

    @app.post("/decisions/{decision_id}/approve")
    def approve_decision(decision_id: int, request: fastapi.Request, body: dict[str, Any] | None = None, rt: runtime.Runtime = runtime_dependency) -> dict[str, Any]:
        roles = run(approvals.decision_roles, rt, decision_id)
        person = current_person(rt, request, roles)
        return run(approvals.approve_decision, rt, decision_id, person,
                   (body or {}).get("option_id"))

    @app.post("/decisions/{decision_id}/reject")
    def reject_decision(decision_id: int, request: fastapi.Request, body: dict[str, Any] | None = None, rt: runtime.Runtime = runtime_dependency) -> dict[str, Any]:
        roles = run(approvals.decision_roles, rt, decision_id)
        person = current_person(rt, request, roles)
        return run(approvals.reject_decision, rt, decision_id, person, reason_of(body))

    @app.post("/emails/{email_id}/approve")
    def approve_email(email_id: int, request: fastapi.Request, body: dict[str, Any] | None = None, rt: runtime.Runtime = runtime_dependency) -> dict[str, Any]:
        person = current_person(rt, request, run(approvals.email_roles, rt, email_id))
        body = body or {}
        return run(approvals.approve_email, rt, email_id, person,
                   body.get("subject"), body.get("body"))

    @app.post("/emails/{email_id}/discard")
    def discard_email(email_id: int, request: fastapi.Request, rt: runtime.Runtime = runtime_dependency) -> dict[str, Any]:
        person = current_person(rt, request, run(approvals.email_roles, rt, email_id))
        return run(approvals.discard_email, rt, email_id, person)

    app.state.current_person = current_person
    app.state.reason_of = reason_of
    app.state.run = run
    return app


def create_default_app() -> fastapi.FastAPI:
    """Factory for `uvicorn --factory`: loads `.env` and the pack."""
    config.load_dotenv()
    return create_app()
