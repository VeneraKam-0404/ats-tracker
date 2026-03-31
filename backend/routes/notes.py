from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.auth import get_current_user
from backend.database import get_db

router = APIRouter(prefix="/api/candidates/{candidate_id}/notes", tags=["notes"])


class NoteCreate(BaseModel):
    content: str


@router.get("")
def list_notes(candidate_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute(
        """SELECT n.*, u.display_name as author_name
           FROM notes n JOIN users u ON n.author_id = u.id
           WHERE n.candidate_id = ?
           ORDER BY n.created_at DESC""",
        (candidate_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("")
def create_note(candidate_id: int, note: NoteCreate, user: dict = Depends(get_current_user)):
    db = get_db()
    cur = db.execute(
        "INSERT INTO notes (candidate_id, author_id, content) VALUES (?, ?, ?)",
        (candidate_id, user["id"], note.content),
    )
    db.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (?, ?, ?, ?)",
        (candidate_id, user["id"], "Добавлена заметка", note.content[:100]),
    )
    db.commit()
    row = db.execute(
        """SELECT n.*, u.display_name as author_name
           FROM notes n JOIN users u ON n.author_id = u.id WHERE n.id = ?""",
        (cur.lastrowid,),
    ).fetchone()
    db.close()
    return dict(row)


@router.delete("/{note_id}")
def delete_note(candidate_id: int, note_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("DELETE FROM notes WHERE id = ? AND candidate_id = ?", (note_id, candidate_id))
    db.commit()
    db.close()
    return {"ok": True}
