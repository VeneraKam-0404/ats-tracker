from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.auth import get_current_user
from backend.database import get_db

router = APIRouter(prefix="/api/candidates", tags=["candidates"])

VALID_STATUSES = ["Новый", "Резюме рассмотрено", "Тестовое задание", "Интервью", "Оффер", "Принят", "Отказ"]


class CandidateCreate(BaseModel):
    full_name: str
    position: str = ""
    email: str = ""
    phone: str = ""
    telegram: str = ""
    status: str = "Новый"
    portfolio_url: str = ""
    source: str = ""


class CandidateUpdate(BaseModel):
    full_name: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    telegram: Optional[str] = None
    status: Optional[str] = None
    portfolio_url: Optional[str] = None
    source: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str


def _candidate_dict(row, db):
    d = dict(row)
    # Fetch ratings
    ratings = db.execute(
        "SELECT r.score, r.user_id, u.display_name FROM ratings r JOIN users u ON r.user_id = u.id WHERE r.candidate_id = ?",
        (d["id"],),
    ).fetchall()
    d["ratings"] = [dict(r) for r in ratings]
    avg = sum(r["score"] for r in ratings) / len(ratings) if ratings else 0
    d["avg_rating"] = round(avg, 1)
    # Last activity
    last = db.execute(
        "SELECT created_at FROM activity_log WHERE candidate_id = ? ORDER BY created_at DESC LIMIT 1",
        (d["id"],),
    ).fetchone()
    d["last_activity"] = last["created_at"] if last else d["created_at"]
    return d


def _log_activity(db, candidate_id, user_id, action, details=""):
    db.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (?, ?, ?, ?)",
        (candidate_id, user_id, action, details),
    )


@router.get("")
def list_candidates(
    status: Optional[str] = None,
    position: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    user: dict = Depends(get_current_user),
):
    db = get_db()
    query = "SELECT * FROM candidates WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if position:
        query += " AND position LIKE ?"
        params.append(f"%{position}%")
    if search:
        query += " AND (full_name LIKE ? OR position LIKE ? OR email LIKE ?)"
        params.extend([f"%{search}%"] * 3)

    allowed_sorts = {"created_at", "full_name", "position", "status", "updated_at"}
    col = sort_by if sort_by in allowed_sorts else "created_at"
    direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
    query += f" ORDER BY {col} {direction}"

    rows = db.execute(query, params).fetchall()
    result = [_candidate_dict(r, db) for r in rows]
    db.close()
    return result


@router.post("")
def create_candidate(c: CandidateCreate, user: dict = Depends(get_current_user)):
    if c.status and c.status not in VALID_STATUSES:
        raise HTTPException(400, "Недопустимый статус")
    db = get_db()
    cur = db.execute(
        """INSERT INTO candidates (full_name, position, email, phone, telegram, status, portfolio_url, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (c.full_name, c.position, c.email, c.phone, c.telegram, c.status, c.portfolio_url, c.source),
    )
    cid = cur.lastrowid
    _log_activity(db, cid, user["id"], "Создан кандидат", f"Добавлен кандидат {c.full_name}")
    db.commit()
    row = db.execute("SELECT * FROM candidates WHERE id = ?", (cid,)).fetchone()
    result = _candidate_dict(row, db)
    db.close()
    return result


@router.get("/{candidate_id}")
def get_candidate(candidate_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    row = db.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Кандидат не найден")
    result = _candidate_dict(row, db)
    db.close()
    return result


@router.put("/{candidate_id}")
def update_candidate(candidate_id: int, c: CandidateUpdate, user: dict = Depends(get_current_user)):
    if c.status and c.status not in VALID_STATUSES:
        raise HTTPException(400, "Недопустимый статус")
    db = get_db()
    existing = db.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "Кандидат не найден")

    updates = {k: v for k, v in c.model_dump().items() if v is not None}
    if not updates:
        db.close()
        return _candidate_dict(existing, db)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [candidate_id]
    db.execute(f"UPDATE candidates SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)

    if "status" in updates:
        _log_activity(db, candidate_id, user["id"], "Статус изменён",
                      f'{existing["status"]} → {updates["status"]}')
    else:
        _log_activity(db, candidate_id, user["id"], "Профиль обновлён", "")

    db.commit()
    row = db.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    result = _candidate_dict(row, db)
    db.close()
    return result


@router.patch("/{candidate_id}/status")
def update_status(candidate_id: int, s: StatusUpdate, user: dict = Depends(get_current_user)):
    if s.status not in VALID_STATUSES:
        raise HTTPException(400, "Недопустимый статус")
    db = get_db()
    existing = db.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "Кандидат не найден")
    db.execute("UPDATE candidates SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
               (s.status, candidate_id))
    _log_activity(db, candidate_id, user["id"], "Статус изменён",
                  f'{existing["status"]} → {s.status}')
    db.commit()
    row = db.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    result = _candidate_dict(row, db)
    db.close()
    return result


@router.delete("/{candidate_id}")
def delete_candidate(candidate_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    existing = db.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "Кандидат не найден")
    db.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
    db.commit()
    db.close()
    return {"ok": True}


@router.get("/{candidate_id}/timeline")
def get_timeline(candidate_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute(
        """SELECT a.*, u.display_name as author_name
           FROM activity_log a JOIN users u ON a.user_id = u.id
           WHERE a.candidate_id = ?
           ORDER BY a.created_at DESC""",
        (candidate_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]
