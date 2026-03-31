import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from backend.auth import get_current_user, get_current_user_from_token
from backend.database import get_db, UPLOAD_PATH

router = APIRouter(prefix="/api/candidates/{candidate_id}/files", tags=["files"])


@router.get("")
def list_files(candidate_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT f.*, u.display_name as uploader_name
           FROM files f JOIN users u ON f.uploaded_by = u.id
           WHERE f.candidate_id = %s
           ORDER BY f.created_at DESC""",
        (candidate_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [{**dict(r), "created_at": str(r["created_at"])} for r in rows]


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

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO files (candidate_id, filename, original_filename, file_type, uploaded_by)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (candidate_id, stored_name, file.filename, file_type, user["id"]),
    )
    fid = cur.fetchone()["id"]
    cur.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
        (candidate_id, user["id"], "Файл загружен", file.filename),
    )
    conn.commit()
    cur.execute(
        """SELECT f.*, u.display_name as uploader_name
           FROM files f JOIN users u ON f.uploaded_by = u.id WHERE f.id = %s""",
        (fid,),
    )
    row = cur.fetchone()
    conn.close()
    return {**dict(row), "created_at": str(row["created_at"])}


@router.get("/{file_id}/download")
def download_file(candidate_id: int, file_id: int, token: str = Query(...)):
    get_current_user_from_token(token)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s AND candidate_id = %s", (file_id, candidate_id))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Файл не найден")
    file_path = UPLOAD_PATH / row["filename"]
    if not file_path.exists():
        raise HTTPException(404, "Файл не найден на диске")
    return FileResponse(str(file_path), filename=row["original_filename"])


@router.delete("/{file_id}")
def delete_file(candidate_id: int, file_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s AND candidate_id = %s", (file_id, candidate_id))
    row = cur.fetchone()
    if row:
        file_path = UPLOAD_PATH / row["filename"]
        if file_path.exists():
            os.remove(file_path)
        cur.execute("DELETE FROM files WHERE id = %s", (file_id,))
        conn.commit()
    conn.close()
    return {"ok": True}
