"""
utils/notifications.py — Email notification helper for court_booker.
"""

import os
import smtplib
from email.message import EmailMessage

from utils.logger import log

NOTIFY_TO = os.environ.get("NOTIFY_EMAIL_TO")
NOTIFY_FROM = os.environ.get("NOTIFY_EMAIL_FROM")
NOTIFY_PASS = os.environ.get("NOTIFY_EMAIL_PASSWORD")


def send_notification(subject: str, body: str, enabled: bool = True):
    if not enabled:
        log(f"Skipping notification (disabled). Subject: {subject}", "DEBUG")
        return
    if not all([NOTIFY_TO, NOTIFY_FROM, NOTIFY_PASS]):
        log(f"Skipping notification (missing env vars). Subject: {subject}", "WARNING")
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = NOTIFY_FROM
        msg["To"] = NOTIFY_TO
        msg.set_content(body)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(NOTIFY_FROM, NOTIFY_PASS)
            server.send_message(msg)
        log(f"Email sent: {subject}")
    except Exception as e:
        log(f"Failed to send notification: {e}", "ERROR")
