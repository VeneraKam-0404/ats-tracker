import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

from backend.database import init_db, UPLOAD_PATH, DATABASE_URL
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


@app.on_event("startup")
def startup():
    init_db()
