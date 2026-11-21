"""HTTP API and cockpit page.

Start it with: python -m soony_tower serve

On a server, set these environment variables:
  COCKPIT_PASSWORD   turns on a browser login (user name: COCKPIT_USER, default "soony")
  SYNC_EVERY         seconds between portal syncs in the background (default 0 = off)
  DOC_READS_PER_SYNC documents Gemini reads after each sync, most important first (default 3)
  MAIL_AUTODRAFT     "0" stops the automatic supplier mail drafts for new risks
"""

import base64
import binascii
import contextlib
import logging
import os
import pathlib
import secrets
import threading

import fastapi
from fastapi import responses
import pandas as pd
import pydantic

from soony_tower import documents
from soony_tower import engine
from soony_tower import mail
from soony_tower import portal
from soony_tower import settings

COCKPIT_DIR = pathlib.Path(__file__).parent / "cockpit"
_OPEN_PATHS = ("/healthz",)

logger = logging.getLogger("soony_tower")
_lock = threading.Lock()  # one sync or rebuild at a time
_latest: dict = {}  # last background result, served to the cockpit
_stop = threading.Event()


def _has_data() -> bool:
    return portal.CURRENT_DIR.exists() and any(portal.CURRENT_DIR.iterdir())


def _cycle() -> dict:
    """Sync, let Gemini read a few documents, recompute and remember risks."""
    with _lock:
        result = engine.run(do_sync=True, remember=True)
        changed = result["file_changes"]
        rerun = False
        reads = int(os.environ.get("DOC_READS_PER_SYNC", "3"))
        if reads > 0 and documents.client_or_none() is not None:
            rerun = bool(documents.read_pending(limit=reads, log=logger.info))
        if mail.credentials() is not None:
            try:
                rerun = bool(mail.poll(log=logger.info)) or rerun
            except mail.MailError as error:
                logger.warning("inbox: %s", error)
        if rerun:
            result = engine.run(do_sync=False, remember=True)
            result["file_changes"] = changed
        if os.environ.get("MAIL_AUTODRAFT", "1") != "0" and result["risk_changes"]["new"]:
            # Drafts only. A person approves every mail before it is sent.
            try:
                mail.draft(result, log=logger.info)
            except (mail.MailError, RuntimeError) as error:
                logger.warning("drafts: %s", error)
        _latest.clear()
        _latest.update(result)
        return result


def _background_loop(every: int) -> None:
    """Keeps the tower current without anyone pressing a button."""
    while not _stop.is_set():
        try:
            result = _cycle()
            logger.info("sync done: %d files changed, %d risks",
                        len(result["file_changes"]), len(result["risks"]))
        except Exception:  # pylint: disable=broad-exception-caught
            # The loop is an isolation boundary: one bad drop must not stop it.
            logger.exception("background sync failed")
        _stop.wait(every)


@contextlib.asynccontextmanager
async def _lifespan(_: fastapi.FastAPI):
    logging.basicConfig(level=logging.INFO)
    every = int(os.environ.get("SYNC_EVERY", "0"))
    if every > 0:
        threading.Thread(target=_background_loop, args=(every,),
                         daemon=True).start()
    yield
    _stop.set()


app = fastapi.FastAPI(title="Soony launch control tower", lifespan=_lifespan)


@app.middleware("http")
async def _require_login(request: fastapi.Request, call_next):
    """HTTP Basic Auth when COCKPIT_PASSWORD is set. The data stays in the team."""
    password = os.environ.get("COCKPIT_PASSWORD")
    if not password or request.url.path in _OPEN_PATHS:
        return await call_next(request)
    user = os.environ.get("COCKPIT_USER", "soony")
    header = request.headers.get("authorization", "")
    if header.lower().startswith("basic "):
        try:
            given = base64.b64decode(header[6:]).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            given = ""
        given_user, _, given_password = given.partition(":")
        if (secrets.compare_digest(given_user, user) and
                secrets.compare_digest(given_password, password)):
            return await call_next(request)
    return responses.Response(
        status_code=401, content="Login required",
        headers={"WWW-Authenticate": 'Basic realm="Soony launch control"'})


def _parse_at(at: str | None) -> pd.Timestamp | None:
    """Reads an optional '2026-11-21T17:00' to replay a moment in a demo."""
    if not at:
        return None
    moment = pd.Timestamp(at)
    return moment.tz_localize(settings.TIMEZONE) if moment.tzinfo is None else moment


def _no_data_yet() -> fastapi.HTTPException:
    return fastapi.HTTPException(
        status_code=503, detail="The first portal sync is still running. Try again in a minute.")


@app.get("/healthz", include_in_schema=False)
def health() -> dict:
    """For the health check of the host. Needs no login."""
    return {"ok": True, "data": _has_data()}


@app.get("/api/status")
def status(at: str | None = None) -> dict:
    """Forecast and risks. Live view uses the last background run if there is one."""
    if not at and _latest:
        return dict(_latest)
    if not _has_data():
        raise _no_data_yet()
    with _lock:
        return engine.run(do_sync=False, at=_parse_at(at), remember=False)


@app.post("/api/sync")
def sync(at: str | None = None) -> dict:
    """Pulls new files from the portal, then recomputes everything."""
    try:
        status_now = _cycle()
    except portal.PortalError as error:
        raise fastapi.HTTPException(status_code=502, detail=str(error)) from error
    if at:
        with _lock:
            replay = engine.run(do_sync=False, at=_parse_at(at), remember=False)
        replay["file_changes"] = status_now["file_changes"]
        replay["risk_changes"] = status_now["risk_changes"]
        return replay
    return status_now


class MailEdit(pydantic.BaseModel):
    """Changes a person makes to a draft before sending it."""
    subject: str | None = None
    body: str | None = None


def _mail_call(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except KeyError as error:
        raise fastapi.HTTPException(status_code=404, detail="No such mail") from error
    except mail.MailError as error:
        raise fastapi.HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:  # every Gemini model busy
        raise fastapi.HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/mail")
def mail_list() -> dict:
    """Every draft, sent mail and reply."""
    state = mail.load_state()
    return {"configured": mail.credentials() is not None,
            "messages": state["messages"], "unmatched": state["unmatched"]}


@app.post("/api/mail/draft")
def mail_draft() -> list[dict]:
    """Lets Gemini write drafts for open risks that no mail covers yet."""
    if not _latest and not _has_data():
        raise _no_data_yet()
    current = _latest or engine.run(do_sync=False, remember=False)
    return _mail_call(mail.draft, current, log=logger.info)


@app.post("/api/mail/{message_id}/send")
def mail_send(message_id: str, edit: MailEdit, request: fastapi.Request) -> dict:
    """A person approved the draft (maybe edited). Send it now."""
    _mail_call(mail.update, message_id, subject=edit.subject, body=edit.body)
    approver = os.environ.get("COCKPIT_USER", "soony") if request.headers.get(
        "authorization") else "local user"
    return _mail_call(mail.send, message_id, approved_by=approver)


@app.post("/api/mail/{message_id}/discard")
def mail_discard(message_id: str) -> dict:
    """The draft is not needed. The risk can get a new draft later."""
    return _mail_call(mail.update, message_id, status="discarded")


@app.post("/api/mail/poll")
def mail_poll() -> dict:
    """Fetches supplier replies now and recomputes the risks."""
    replies = _mail_call(mail.poll, log=logger.info)
    if replies and _has_data():
        with _lock:
            _latest.clear()
            _latest.update(engine.run(do_sync=False, remember=True))
    return {"new_replies": len(replies)}


@app.get("/api/changes")
def changes() -> list[dict]:
    """Every file change detected so far."""
    return [engine.to_jsonable(c) for c in portal.read_changes()]


@app.get("/", include_in_schema=False)
def cockpit() -> responses.FileResponse:
    """The cockpit page. It reads /api/status in the browser."""
    return responses.FileResponse(COCKPIT_DIR / "index.html")
