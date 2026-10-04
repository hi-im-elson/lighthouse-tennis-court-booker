import os
import smtplib
import uuid
from datetime import datetime
from email.message import EmailMessage

import pytz

from utils.logger import log

NOTIFY_TO = os.environ.get("NOTIFY_EMAIL_TO")
NOTIFY_FROM = os.environ.get("NOTIFY_EMAIL_FROM")
NOTIFY_PASS = os.environ.get("NOTIFY_EMAIL_PASSWORD")


def create_ics_attachment(
    target_date: str,
    start_time: str,
    end_time: str,
    tz_name: str = "America/Toronto",
    title: str = "Tennis at Condo",
) -> tuple[str, bytes]:
    tz = pytz.timezone(tz_name)

    start = tz.localize(
        datetime.strptime(f"{target_date} {start_time}", "%Y-%m-%d %H:%M")
    )
    end = tz.localize(
        datetime.strptime(f"{target_date} {end_time}", "%Y-%m-%d %H:%M")
    )

    def ics_datetime(value: datetime) -> str:
        return value.astimezone(pytz.UTC).strftime("%Y%m%dT%H%M%SZ")

    now = datetime.now(pytz.UTC)

    ics = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Court Booker//Tennis Booking//EN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{uuid.uuid4()}@court-booker",
            f"DTSTAMP:{ics_datetime(now)}",
            f"DTSTART:{ics_datetime(start)}",
            f"DTEND:{ics_datetime(end)}",
            f"SUMMARY:{title}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )

    filename = f"tennis_at_condo_{target_date}.ics"
    return filename, ics.encode("utf-8")


def send_notification(
    subject: str,
    body: str,
    enabled: bool = True,
    attachment: tuple[str, bytes] | None = None,
):
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

        if attachment:
            filename, content = attachment
            msg.add_attachment(
                content,
                maintype="text",
                subtype="calendar",
                filename=filename,
            )

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(NOTIFY_FROM, NOTIFY_PASS)
            server.send_message(msg)

        log(f"Email sent: {subject}")

    except Exception as e:
        log(f"Failed to send notification: {e}", "ERROR")
