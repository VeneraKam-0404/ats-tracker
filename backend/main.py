import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

from fastapi import Depends
from backend.database import init_db, get_db, UPLOAD_PATH, DATABASE_URL
from backend.auth import get_current_user
from backend.routes import auth, candidates, notes, meetings, tasks, files, ratings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ats")

app = FastAPI(title="ATS Tracker", version="1.0.0")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.include_router(auth.router)
app.include_router(candidates.router)
app.include_router(notes.router)
app.include_router(meetings.router)
app.include_router(tasks.router)
app.include_router(files.router)
app.include_router(ratings.router)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/health")
def health():
    import os
    from backend.database import get_db
    db_ok = False
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        db_ok = True
        conn.close()
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "db_error",
        "database": "connected" if db_ok else "failed",
        "database_url_set": bool(DATABASE_URL),
        "upload_path": str(UPLOAD_PATH),
        "upload_dir_writable": os.access(UPLOAD_PATH, os.W_OK),
    }


@app.get("/api/meetings")
def all_meetings(date_from: str = "", date_to: str = "", user: dict = Depends(get_current_user)):
    """Get all meetings across all candidates, optionally filtered by date range."""
    conn = get_db()
    cur = conn.cursor()
    query = """SELECT m.*, c.full_name as candidate_name, c.position as candidate_position,
                      u.display_name as creator_name
               FROM meetings m
               JOIN candidates c ON m.candidate_id = c.id
               JOIN users u ON m.created_by = u.id
               WHERE 1=1"""
    params = []
    if date_from:
        query += " AND m.meeting_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND m.meeting_date <= %s"
        params.append(date_to)
    query += " ORDER BY m.meeting_date ASC, m.meeting_time ASC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [{**dict(r), "created_at": str(r["created_at"])} for r in rows]


@app.on_event("startup")
def startup():
    init_db()
