from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.auth import get_current_user
from backend.database import get_db

router = APIRouter(prefix="/api/candidates/{candidate_id}/meetings", tags=["meetings"])


class MeetingCreate(BaseModel):
    meeting_date: str
    format: str = "zoom"
    recording_url: str = ""
    summary: str = ""


class MeetingUpdate(BaseModel):
    meeting_date: Optional[str] = None
    format: Optional[str] = None
    recording_url: Optional[str] = None
    summary: Optional[str] = None


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
    cur.execute(
        """INSERT INTO meetings (candidate_id, meeting_date, format, recording_url, summary, created_by)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (candidate_id, m.meeting_date, m.format, m.recording_url, m.summary, user["id"]),
    )
    mid = cur.fetchone()["id"]
    cur.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
        (candidate_id, user["id"], "Добавлена встреча", f"{m.meeting_date} ({m.format})"),
    )
    conn.commit()
    cur.execute(
        """SELECT m.*, u.display_name as creator_name
           FROM meetings m JOIN users u ON m.created_by = u.id WHERE m.id = %s""",
        (mid,),
    )
    row = cur.fetchone()
    conn.close()
    return {**dict(row), "created_at": str(row["created_at"])}


@router.put("/{meeting_id}")
def update_meeting(candidate_id: int, meeting_id: int, m: MeetingUpdate, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    updates = {k: v for k, v in m.model_dump().items() if v is not None}
    if updates:
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [meeting_id, candidate_id]
        cur.execute(f"UPDATE meetings SET {set_clause} WHERE id = %s AND candidate_id = %s", values)
        conn.commit()
    cur.execute(
        """SELECT m.*, u.display_name as creator_name
           FROM meetings m JOIN users u ON m.created_by = u.id WHERE m.id = %s""",
        (meeting_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Встреча не найдена")
    return {**dict(row), "created_at": str(row["created_at"])}


@router.delete("/{meeting_id}")
def delete_meeting(candidate_id: int, meeting_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM meetings WHERE id = %s AND candidate_id = %s", (meeting_id, candidate_id))
    conn.commit()
    conn.close()
    return {"ok": True}
