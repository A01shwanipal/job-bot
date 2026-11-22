import logging
import smtplib
from email.message import EmailMessage

import requests

from .config import env

log = logging.getLogger(__name__)


def send_email(subject: str, body: str) -> bool:
    host, user, pw, to = env("SMTP_HOST"), env("SMTP_USER"), env("SMTP_PASSWORD"), env("MAIL_TO")
    if not (host and user and pw and to):
        log.warning("e-mail not configured (SMTP_* / MAIL_TO in .env)")
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL(host, int(env("SMTP_PORT", "465")), timeout=30) as s:
            s.login(user, pw)
            s.send_message(msg)
        return True
    except Exception as e:
        log.error("e-mail failed: %s", e)
        return False


def send_telegram(body: str) -> bool:
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not (token and chat):
        log.warning("Telegram not configured")
        return False
    try:
        for i in range(0, len(body), 3800):
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              json={"chat_id": chat, "text": body[i:i + 3800], "disable_web_page_preview": True},
                              timeout=20)
            r.raise_for_status()
        return True
    except Exception as e:
        log.error("Telegram failed: %s", e)
        return False


def notify(settings: dict, text: str) -> None:
    n = settings.get("notifications", {})
    if n.get("email"):
        send_email("Job Bot daily summary", text)
    if n.get("telegram"):
        send_telegram(text)
