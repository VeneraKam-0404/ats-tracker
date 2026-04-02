import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.auth import get_current_user
from backend.database import get_db
from backend.email_service import send_meeting_email, is_email_configured

logger = logging.getLogger("ats")

router = APIRouter(prefix="/api/candidates/{candidate_id}/meetings", tags=["meetings"])


class MeetingCreate(BaseModel):
    meeting_date: str
    meeting_time: str = ""
    format: str = "zoom"
    zoom_url: str = ""
    recording_url: str = ""
    summary: str = ""
    attendees: str = "all"
    duration: int = 60


class MeetingUpdate(BaseModel):
    meeting_date: Optional[str] = None
    meeting_time: Optional[str] = None
    format: Optional[str] = None
    zoom_url: Optional[str] = None
    recording_url: Optional[str] = None
    summary: Optional[str] = None
    attendees: Optional[str] = None
    duration: Optional[int] = None


def _get_candidate(cur, candidate_id):
    cur.execute("SELECT * FROM candidates WHERE id = %s", (candidate_id,))
    return cur.fetchone()


def _get_all_user_emails(cur):
    cur.execute("SELECT email FROM users WHERE email IS NOT NULL AND email != ''")
    return [r["email"] for r in cur.fetchall()]


def _send_invite(cur, meeting, candidate, method="REQUEST", cancel=False):
    """Send calendar invite for a meeting. Fails silently."""
    try:
        user_emails = _get_all_user_emails(cur)
        send_meeting_email(
            meeting_id=meeting["id"],
            candidate_name=candidate["full_name"],
            candidate_email=candidate.get("email", ""),
            position=candidate.get("position", ""),
            meeting_date=meeting["meeting_date"],
            meeting_time=meeting.get("meeting_time", ""),
            meeting_format=meeting["format"],
            zoom_url=meeting.get("zoom_url", "") or meeting.get("recording_url", ""),
            user_emails=user_emails,
            method=method,
            cancel=cancel,
            sequence=meeting.get("ics_sequence", 0),
            duration_minutes=meeting.get("duration") or 60,
        )
    except Exception as e:
        logger.error(f"Failed to send meeting invite: {e}")


@router.get("")
def list_meetings(candidate_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT m.*, u.display_name as creator_name
           FROM meetings m JOIN users u ON m.created_by = u.id
           WHERE m.candidate_id = %s
           ORDER BY m.meeting_date DESC""",
        (candidate_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [{**dict(r), "created_at": str(r["created_at"])} for r in rows]


@router.post("")
def create_meeting(candidate_id: int, m: MeetingCreate, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    candidate = _get_candidate(cur, candidate_id)
    if not candidate:
        conn.close()
        raise HTTPException(404, "Кандидат не найден")

    cur.execute(
        """INSERT INTO meetings (candidate_id, meeting_date, meeting_time, format, zoom_url, recording_url, summary, attendees, duration, created_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (candidate_id, m.meeting_date, m.meeting_time, m.format, m.zoom_url, m.recording_url, m.summary, m.attendees, m.duration, user["id"]),
    )
    mid = cur.fetchone()["id"]
    cur.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
        (candidate_id, user["id"], "Добавлена встреча", f"{m.meeting_date} {m.meeting_time} ({m.format}, {m.duration} мин)"),
    )
    conn.commit()

    cur.execute(
        """SELECT m.*, u.display_name as creator_name
           FROM meetings m JOIN users u ON m.created_by = u.id WHERE m.id = %s""",
        (mid,),
    )
    meeting = cur.fetchone()

    _send_invite(cur, meeting, candidate)

    conn.close()
    return {**dict(meeting), "created_at": str(meeting["created_at"]), "email_configured": is_email_configured()}


@router.put("/{meeting_id}")
def update_meeting(candidate_id: int, meeting_id: int, m: MeetingUpdate, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM meetings WHERE id = %s AND candidate_id = %s", (meeting_id, candidate_id))
    existing = cur.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404, "Встреча не найдена")

    candidate = _get_candidate(cur, candidate_id)

    updates = {k: v for k, v in m.model_dump().items() if v is not None}

    if not updates:
        conn.close()
        return {**dict(existing), "created_at": str(existing["created_at"])}

    # Check if date/time changed for reschedule log
    old_date = existing["meeting_date"]
    old_time = existing.get("meeting_time", "")
    new_date = updates.get("meeting_date", old_date)
    new_time = updates.get("meeting_time", old_time)
    rescheduled = (new_date != old_date) or (new_time != old_time)

    # Bump ICS sequence for calendar update
    new_seq = (existing.get("ics_sequence") or 0) + 1
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [new_seq, meeting_id, candidate_id]
    cur.execute(
        f"UPDATE meetings SET {set_clause}, ics_sequence = %s WHERE id = %s AND candidate_id = %s",
        values,
    )

    if rescheduled:
        cur.execute(
            "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
            (candidate_id, user["id"], "Встреча перенесена",
             f"было {old_date} {old_time} → стало {new_date} {new_time}"),
        )
    else:
        cur.execute(
            "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
            (candidate_id, user["id"], "Встреча обновлена",
             f"{new_date} {new_time} ({updates.get('format', existing['format'])})"),
        )

    conn.commit()

    cur.execute(
        """SELECT m.*, u.display_name as creator_name
           FROM meetings m JOIN users u ON m.created_by = u.id WHERE m.id = %s""",
        (meeting_id,),
    )
    meeting = cur.fetchone()

    # Send updated invite to all participants
    if candidate:
        _send_invite(cur, meeting, candidate, method="REQUEST")

    conn.close()
    return {**dict(meeting), "created_at": str(meeting["created_at"])}


@router.delete("/{meeting_id}")
def delete_meeting(candidate_id: int, meeting_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM meetings WHERE id = %s AND candidate_id = %s", (meeting_id, candidate_id))
    meeting = cur.fetchone()
    candidate = _get_candidate(cur, candidate_id)

    if meeting and candidate:
        cancel_meeting = dict(meeting)
        cancel_meeting["ics_sequence"] = (cancel_meeting.get("ics_sequence") or 0) + 1
        _send_invite(cur, cancel_meeting, candidate, cancel=True)

        cur.execute(
            "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
            (candidate_id, user["id"], "Встреча отменена",
             f"{meeting['meeting_date']} {meeting.get('meeting_time', '')} ({meeting['format']})"),
        )

    cur.execute("DELETE FROM meetings WHERE id = %s AND candidate_id = %s", (meeting_id, candidate_id))
    conn.commit()
    conn.close()
    return {"ok": True}
