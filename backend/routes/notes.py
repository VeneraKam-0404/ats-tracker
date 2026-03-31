from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.auth import get_current_user
from backend.database import get_db

router = APIRouter(prefix="/api/candidates/{candidate_id}/notes", tags=["notes"])


class NoteCreate(BaseModel):
    content: str


@router.get("")
def list_notes(candidate_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT n.*, u.display_name as author_name
           FROM notes n JOIN users u ON n.author_id = u.id
           WHERE n.candidate_id = %s
           ORDER BY n.created_at DESC""",
        (candidate_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [{**dict(r), "created_at": str(r["created_at"])} for r in rows]


@router.post("")
def create_note(candidate_id: int, note: NoteCreate, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO notes (candidate_id, author_id, content) VALUES (%s, %s, %s) RETURNING id",
        (candidate_id, user["id"], note.content),
    )
    nid = cur.fetchone()["id"]
    cur.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
        (candidate_id, user["id"], "Добавлена заметка", note.content[:100]),
    )
    conn.commit()
    cur.execute(
        """SELECT n.*, u.display_name as author_name
           FROM notes n JOIN users u ON n.author_id = u.id WHERE n.id = %s""",
        (nid,),
    )
    row = cur.fetchone()
    conn.close()
    return {**dict(row), "created_at": str(row["created_at"])}


@router.delete("/{note_id}")
def delete_note(candidate_id: int, note_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM notes WHERE id = %s AND candidate_id = %s", (note_id, candidate_id))
    conn.commit()
    conn.close()
    return {"ok": True}
