import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from backend.auth import get_current_user
from backend.database import get_db, UPLOAD_PATH

router = APIRouter(prefix="/api/candidates/{candidate_id}/files", tags=["files"])


@router.get("")
def list_files(candidate_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute(
        """SELECT f.*, u.display_name as uploader_name
           FROM files f JOIN users u ON f.uploaded_by = u.id
           WHERE f.candidate_id = ?
           ORDER BY f.created_at DESC""",
        (candidate_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("")
async def upload_file(
    candidate_id: int,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    stored_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_PATH / stored_name

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    file_type = "resume" if ext.lower() == ".pdf" else "other"

    db = get_db()
    cur = db.execute(
        """INSERT INTO files (candidate_id, filename, original_filename, file_type, uploaded_by)
           VALUES (?, ?, ?, ?, ?)""",
        (candidate_id, stored_name, file.filename, file_type, user["id"]),
    )
    db.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (?, ?, ?, ?)",
        (candidate_id, user["id"], "Файл загружен", file.filename),
    )
    db.commit()
    row = db.execute(
        """SELECT f.*, u.display_name as uploader_name
           FROM files f JOIN users u ON f.uploaded_by = u.id WHERE f.id = ?""",
        (cur.lastrowid,),
    ).fetchone()
    db.close()
    return dict(row)


@router.get("/{file_id}/download")
def download_file(candidate_id: int, file_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    row = db.execute("SELECT * FROM files WHERE id = ? AND candidate_id = ?", (file_id, candidate_id)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Файл не найден")
    file_path = UPLOAD_PATH / row["filename"]
    if not file_path.exists():
        raise HTTPException(404, "Файл не найден на диске")
    return FileResponse(str(file_path), filename=row["original_filename"])


@router.delete("/{file_id}")
def delete_file(candidate_id: int, file_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    row = db.execute("SELECT * FROM files WHERE id = ? AND candidate_id = ?", (file_id, candidate_id)).fetchone()
    if row:
        file_path = UPLOAD_PATH / row["filename"]
        if file_path.exists():
            os.remove(file_path)
        db.execute("DELETE FROM files WHERE id = ?", (file_id,))
        db.commit()
    db.close()
    return {"ok": True}
