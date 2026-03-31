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
    db = get_db()
    rows = db.execute(
        """SELECT m.*, u.display_name as creator_name
           FROM meetings m JOIN users u ON m.created_by = u.id
           WHERE m.candidate_id = ?
           ORDER BY m.meeting_date DESC""",
        (candidate_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("")
def create_meeting(candidate_id: int, m: MeetingCreate, user: dict = Depends(get_current_user)):
    db = get_db()
    cur = db.execute(
        """INSERT INTO meetings (candidate_id, meeting_date, format, recording_url, summary, created_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (candidate_id, m.meeting_date, m.format, m.recording_url, m.summary, user["id"]),
    )
    db.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (?, ?, ?, ?)",
        (candidate_id, user["id"], "Добавлена встреча", f"{m.meeting_date} ({m.format})"),
    )
    db.commit()
    row = db.execute(
        """SELECT m.*, u.display_name as creator_name
           FROM meetings m JOIN users u ON m.created_by = u.id WHERE m.id = ?""",
        (cur.lastrowid,),
    ).fetchone()
    db.close()
    return dict(row)


@router.put("/{meeting_id}")
def update_meeting(candidate_id: int, meeting_id: int, m: MeetingUpdate, user: dict = Depends(get_current_user)):
    db = get_db()
    updates = {k: v for k, v in m.model_dump().items() if v is not None}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [meeting_id, candidate_id]
        db.execute(f"UPDATE meetings SET {set_clause} WHERE id = ? AND candidate_id = ?", values)
        db.commit()
    row = db.execute(
        """SELECT m.*, u.display_name as creator_name
           FROM meetings m JOIN users u ON m.created_by = u.id WHERE m.id = ?""",
        (meeting_id,),
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Встреча не найдена")
    return dict(row)


@router.delete("/{meeting_id}")
def delete_meeting(candidate_id: int, meeting_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("DELETE FROM meetings WHERE id = ? AND candidate_id = ?", (meeting_id, candidate_id))
    db.commit()
    db.close()
    return {"ok": True}
