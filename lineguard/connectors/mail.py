"""Port for mail: send and poll, with the modes DRY_RUN, LIVE and REPLAY.

DRY_RUN writes mails only to the log (the default). LIVE uses SMTP and
IMAP. REPLAY sends nothing and reads recorded replies from `.eml` files,
for a demo without network (architecture.md §7.2, §10).
"""

import email
import email.message
import email.policy
import email.utils
import imaplib
import logging
import pathlib
import smtplib

from lineguard import config

logger = logging.getLogger(__name__)
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465
IMAP_HOST = "imap.gmail.com"


class MailError(Exception):
    """A mail cannot be sent or the inbox cannot be read."""


class Mailer:
    """Sends approved mails and returns new incoming mails."""

    def __init__(self, mode: str, address: str, password: str, sender_name: str, replay_folder: pathlib.Path):
        self.mode = mode if mode in ("LIVE", "REPLAY") else "DRY_RUN"
        self.address = address or "lineguard@localhost"
        self._password = password
        self._sender_name = sender_name
        self._replay_folder = replay_folder

    def new_message_id(self) -> str:
        return email.utils.make_msgid(domain=self.address.split("@")[-1])

    def send(self, to_addr: str, subject: str, body: str, message_id: str, in_reply_to: str | None = None) -> str:
        """Sends one mail. Returns the status: 'sent' or 'dry_run'."""
        if self.mode != "LIVE":
            logger.info("Mail not sent (%s): to %s, subject %s", self.mode, to_addr, subject)
            return "dry_run"
        message = email.message.EmailMessage()
        message["From"] = email.utils.formataddr((self._sender_name, self.address))
        message["To"] = to_addr
        message["Subject"] = subject
        message["Date"] = email.utils.formatdate(localtime=True)
        message["Message-ID"] = message_id
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to
        message.set_content(body)
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
                smtp.login(self.address, self._password)
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError) as error:
            raise MailError(f"Sending to '{to_addr}' failed: {error}") from error
        return "sent"

    def poll(self, senders: list[str], known_ids: set[str]) -> list[email.message.EmailMessage]:
        """Returns mails that are not known yet.

        Args:
            senders: Addresses of the contacts. LIVE reads only their mails.
            known_ids: Message-IDs that are stored already.
        """
        if self.mode == "LIVE":
            return self._poll_imap(senders, known_ids)
        if self.mode == "REPLAY":
            return self._poll_folder(known_ids)
        return []

    def _poll_folder(self, known_ids: set[str]) -> list[email.message.EmailMessage]:
        found = []
        for path in sorted(self._replay_folder.glob("*.eml")):
            message = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
            if message.get("Message-ID") not in known_ids:
                found.append(message)
        return found

    def _poll_imap(self, senders: list[str], known_ids: set[str]) -> list[email.message.EmailMessage]:
        found = []
        try:
            with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
                imap.login(self.address, self._password)
                imap.select("INBOX", readonly=True)
                for sender in sorted(set(senders)):
                    _, data = imap.uid("search", None, f'(FROM "{sender}")')
                    for uid in (data[0] or b"").split():
                        _, head = imap.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
                        header = email.message_from_bytes(head[0][1])
                        if header.get("Message-ID") in known_ids:
                            continue
                        _, fetched = imap.uid("fetch", uid, "(RFC822)")
                        found.append(email.message_from_bytes(
                            fetched[0][1], policy=email.policy.default))
        except (imaplib.IMAP4.error, OSError) as error:
            raise MailError(f"Reading the inbox failed: {error}") from error
        return found


def from_pack(sender_env: str, sender_name: str, workspace: str) -> Mailer:
    """Builds the mailer from `.env` and the pack."""
    return Mailer(
        mode=config.get("MAIL_MODE", "DRY_RUN"),
        address=config.get(sender_env), password=config.get("GMAIL_APP_PASSWORD"),
        sender_name=sender_name,
        replay_folder=config.data_dir(workspace) / "demo" / "inbox")
