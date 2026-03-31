from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from backend.database import init_db
from backend.routes import auth, candidates, notes, meetings, tasks, files, ratings

app = FastAPI(title="ATS Tracker", version="1.0.0")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

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


@app.on_event("startup")
def startup():
    init_db()
