"""Read-only inbox scan: marks applied jobs as 'interview' / 'rejected' when a mail from that company says so.
Keyword based, so it can be wrong - the event note says which mail triggered it. Check in the dashboard."""
import email
import imaplib
import logging
import re
from datetime import datetime, timedelta
from email.header import decode_header, make_header

from . import db
from .config import env

log = logging.getLogger(__name__)
INTERVIEW = re.compile(r"interview|shortlisted|schedule a call|technical round|assessment link|next round", re.I)
REJECT = re.compile(r"unfortunately|not (be )?moving forward|regret to inform|other candidates|not selected", re.I)


def _text(msg) -> str:
    parts = []
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            try:
                parts.append(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore"))
            except Exception:
                pass
    return " ".join(parts)[:3000]


def run(days: int = 3) -> int:
    host, user, pw = env("IMAP_HOST", "imap.gmail.com"), env("IMAP_USER"), env("IMAP_PASSWORD")
    if not (user and pw):
        log.warning("IMAP not configured - skipping inbox check")
        return 0
    jobs = [j for j in db.list_jobs(["applied"]) if len(j["company"]) >= 4]
    if not jobs:
        return 0
    changed = 0
    M = imaplib.IMAP4_SSL(host)
    try:
        M.login(user, pw)
        M.select("INBOX", readonly=True)
        since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        _, data = M.search(None, f'(SINCE "{since}")')
        for num in data[0].split():
            _, raw = M.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(raw[0][1])
            subject = str(make_header(decode_header(msg.get("Subject", ""))))
            blob = f"{msg.get('From', '')} {subject} {_text(msg)}".lower()
            for j in jobs:
                if j["status"] != "applied" or j["company"].lower() not in blob:
                    continue
                if INTERVIEW.search(blob):
                    db.set_status(j["id"], "interview", f"mail: {subject[:80]}")
                    changed += 1
                elif REJECT.search(blob):
                    db.set_status(j["id"], "rejected", f"mail: {subject[:80]}")
                    changed += 1
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return changed
