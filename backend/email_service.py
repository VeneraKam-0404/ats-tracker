import os
import smtplib
import logging
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta

logger = logging.getLogger("ats")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")


def is_email_configured():
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def generate_ics(
    meeting_id: int,
    candidate_name: str,
    position: str,
    meeting_date: str,
    meeting_time: str,
    meeting_format: str,
    zoom_url: str,
    attendee_emails: list[str],
    organizer_email: str,
    method: str = "REQUEST",
    status: str = "CONFIRMED",
    sequence: int = 0,
):
    """Generate an iCalendar .ics file content."""
    # Parse date and time
    try:
        if meeting_time:
            dt_start = datetime.strptime(f"{meeting_date} {meeting_time}", "%Y-%m-%d %H:%M")
        else:
            dt_start = datetime.strptime(meeting_date, "%Y-%m-%d").replace(hour=10, minute=0)
    except ValueError:
        dt_start = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

    dt_end = dt_start + timedelta(hours=1)
    dt_stamp = datetime.utcnow()

    uid = f"ats-meeting-{meeting_id}@ats-tracker"

    summary = f"Интервью: {candidate_name}"
    if position:
        summary += f" — {position}"

    description = f"Формат: {meeting_format}"
    if zoom_url:
        description += f"\\nСсылка: {zoom_url}"

    location = zoom_url if meeting_format == "zoom" and zoom_url else meeting_format

    attendees = ""
    for email in attendee_emails:
        if email:
            attendees += f"ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:{email}\n"

    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//ATS Tracker//Meeting//RU
METHOD:{method}
BEGIN:VEVENT
UID:{uid}
DTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}
DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}
DTSTAMP:{dt_stamp.strftime('%Y%m%dT%H%M%SZ')}
ORGANIZER:mailto:{organizer_email}
{attendees}SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:{location}
STATUS:{status}
SEQUENCE:{sequence}
END:VEVENT
END:VCALENDAR"""
    return ics.strip()


def send_meeting_email(
    meeting_id: int,
    candidate_name: str,
    candidate_email: str,
    position: str,
    meeting_date: str,
    meeting_time: str,
    meeting_format: str,
    zoom_url: str,
    user_emails: list[str],
    method: str = "REQUEST",
    cancel: bool = False,
    sequence: int = 0,
):
    """Send calendar invite email to all participants."""
    if not is_email_configured():
        logger.warning("SMTP not configured, skipping email send")
        return False

    organizer_email = SMTP_USER
    all_emails = [e for e in user_emails + [candidate_email] if e]
    if not all_emails:
        logger.warning("No recipient emails, skipping")
        return False

    ics_status = "CANCELLED" if cancel else "CONFIRMED"
    ics_method = "CANCEL" if cancel else method

    ics_content = generate_ics(
        meeting_id=meeting_id,
        candidate_name=candidate_name,
        position=position,
        meeting_date=meeting_date,
        meeting_time=meeting_time,
        meeting_format=meeting_format,
        zoom_url=zoom_url,
        attendee_emails=all_emails,
        organizer_email=organizer_email,
        method=ics_method,
        status=ics_status,
        sequence=sequence,
    )

    subject_prefix = "Отмена: " if cancel else ("Обновление: " if method == "REQUEST" and sequence > 0 else "")
    subject = f"{subject_prefix}Интервью: {candidate_name}"
    if position:
        subject += f" — {position}"

    # Build email body
    time_str = meeting_time or "10:00"
    body_lines = [
        f"{'Встреча отменена' if cancel else 'Приглашение на интервью'}",
        f"",
        f"Кандидат: {candidate_name}",
        f"Позиция: {position}" if position else None,
        f"Дата: {meeting_date}",
        f"Время: {time_str}",
        f"Формат: {meeting_format}",
        f"Ссылка: {zoom_url}" if zoom_url else None,
        f"",
        f"Календарное приглашение прикреплено к письму (.ics)",
    ]
    body = "\n".join(line for line in body_lines if line is not None)

    try:
        for recipient in all_emails:
            msg = MIMEMultipart("mixed")
            msg["From"] = SMTP_USER
            msg["To"] = recipient
            msg["Subject"] = subject

            # Text body
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # ICS as alternative (so calendar apps pick it up)
            ics_part = MIMEText(ics_content, "calendar", "utf-8")
            ics_part.add_header("Content-Disposition", "inline")
            ics_part.set_param("method", ics_method)
            msg.attach(ics_part)

            # ICS as attachment (fallback)
            attachment = MIMEBase("application", "ics")
            attachment.set_payload(ics_content.encode("utf-8"))
            encoders.encode_base64(attachment)
            filename = "cancel.ics" if cancel else "invite.ics"
            attachment.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(attachment)

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"Meeting email sent to {recipient}")

        return True
    except Exception as e:
        logger.error(f"Failed to send meeting email: {e}")
        return False
