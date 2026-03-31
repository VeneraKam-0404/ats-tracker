import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.auth import get_current_user
from backend.database import get_db

logger = logging.getLogger("ats")

router = APIRouter(prefix="/api/candidates", tags=["candidates"])

VALID_STATUSES = [
    "Новый", "Резюме рассмотрено", "Запрос информации",
    "Тестовое задание", "Интервью", "Оффер", "Принят", "Отказ",
]

APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:8000")


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
    note: str = ""


def _candidate_dict(row, cur):
    d = dict(row)
    cur.execute(
        "SELECT r.score, r.user_id, u.display_name FROM ratings r JOIN users u ON r.user_id = u.id WHERE r.candidate_id = %s",
        (d["id"],),
    )
    ratings = cur.fetchall()
    d["ratings"] = [dict(r) for r in ratings]
    avg = sum(r["score"] for r in ratings) / len(ratings) if ratings else 0
    d["avg_rating"] = round(avg, 1)
    cur.execute(
        "SELECT created_at FROM activity_log WHERE candidate_id = %s ORDER BY created_at DESC LIMIT 1",
        (d["id"],),
    )
    last = cur.fetchone()
    d["last_activity"] = str(last["created_at"]) if last else str(d["created_at"])
    for k in ("created_at", "updated_at"):
        if d.get(k):
            d[k] = str(d[k])
    return d


def _log_activity(cur, candidate_id, user_id, action, details=""):
    cur.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
        (candidate_id, user_id, action, details),
    )


def _notify_status_change(cur, candidate, old_status, new_status, changed_by, note=""):
    """Send email to the OTHER user when status changes."""
    from backend.email_service import is_email_configured, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
    if not is_email_configured():
        return

    import smtplib
    from email.mime.text import MIMEText

    # Get all users except the one who made the change
    cur.execute("SELECT email, display_name FROM users WHERE id != %s AND email IS NOT NULL AND email != ''",
                (changed_by["id"],))
    recipients = cur.fetchall()
    if not recipients:
        return

    candidate_name = candidate["full_name"]
    subject = f"[ATS] Статус изменён: {candidate_name} → {new_status}"

    body_lines = [
        f"{changed_by['display_name']} изменил(а) статус кандидата:",
        f"",
        f"Кандидат: {candidate_name}",
        f"Позиция: {candidate.get('position', '')}",
        f"Статус: {old_status} → {new_status}",
    ]
    if note:
        body_lines += [f"", f"Комментарий: {note}"]
    body_lines += [f"", f"Открыть в ATS: {APP_URL}"]

    body = "\n".join(body_lines)

    try:
        for r in recipients:
            msg = MIMEText(body, "plain", "utf-8")
            msg["From"] = SMTP_USER
            msg["To"] = r["email"]
            msg["Subject"] = subject
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            logger.info(f"Status change email sent to {r['email']}")
    except Exception as e:
        logger.error(f"Failed to send status change email: {e}")


@router.get("")
def list_candidates(
    status: Optional[str] = None,
    position: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    user: dict = Depends(get_current_user),
):
    conn = get_db()
    cur = conn.cursor()
    query = "SELECT * FROM candidates WHERE 1=1"
    params = []
    if status:
        query += " AND status = %s"
        params.append(status)
    if position:
        query += " AND position ILIKE %s"
        params.append(f"%{position}%")
    if search:
        query += " AND (full_name ILIKE %s OR position ILIKE %s OR email ILIKE %s)"
        params.extend([f"%{search}%"] * 3)

    allowed_sorts = {"created_at", "full_name", "position", "status", "updated_at"}
    col = sort_by if sort_by in allowed_sorts else "created_at"
    direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
    query += f" ORDER BY {col} {direction}"

    cur.execute(query, params)
    rows = cur.fetchall()
    result = [_candidate_dict(r, cur) for r in rows]
    conn.close()
    return result


@router.post("")
def create_candidate(c: CandidateCreate, user: dict = Depends(get_current_user)):
    if c.status and c.status not in VALID_STATUSES:
        raise HTTPException(400, "Недопустимый статус")
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO candidates (full_name, position, email, phone, telegram, status, portfolio_url, source)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (c.full_name, c.position, c.email, c.phone, c.telegram, c.status, c.portfolio_url, c.source),
    )
    cid = cur.fetchone()["id"]
    _log_activity(cur, cid, user["id"], "Создан кандидат", f"Добавлен кандидат {c.full_name}")
    conn.commit()
    cur.execute("SELECT * FROM candidates WHERE id = %s", (cid,))
    row = cur.fetchone()
    result = _candidate_dict(row, cur)
    conn.close()
    return result


@router.get("/{candidate_id}")
def get_candidate(candidate_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM candidates WHERE id = %s", (candidate_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Кандидат не найден")
    result = _candidate_dict(row, cur)
    conn.close()
    return result


@router.put("/{candidate_id}")
def update_candidate(candidate_id: int, c: CandidateUpdate, user: dict = Depends(get_current_user)):
    if c.status and c.status not in VALID_STATUSES:
        raise HTTPException(400, "Недопустимый статус")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM candidates WHERE id = %s", (candidate_id,))
    existing = cur.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404, "Кандидат не найден")

    updates = {k: v for k, v in c.model_dump().items() if v is not None}
    if not updates:
        conn.close()
        return _candidate_dict(existing, cur)

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [candidate_id]
    cur.execute(f"UPDATE candidates SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = %s", values)

    if "status" in updates:
        _log_activity(cur, candidate_id, user["id"], "Статус изменён",
                      f'{existing["status"]} → {updates["status"]}')
        _notify_status_change(cur, existing, existing["status"], updates["status"], user)
    else:
        _log_activity(cur, candidate_id, user["id"], "Профиль обновлён", "")

    conn.commit()
    cur.execute("SELECT * FROM candidates WHERE id = %s", (candidate_id,))
    row = cur.fetchone()
    result = _candidate_dict(row, cur)
    conn.close()
    return result


@router.patch("/{candidate_id}/status")
def update_status(candidate_id: int, s: StatusUpdate, user: dict = Depends(get_current_user)):
    if s.status not in VALID_STATUSES:
        raise HTTPException(400, "Недопустимый статус")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM candidates WHERE id = %s", (candidate_id,))
    existing = cur.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404, "Кандидат не найден")

    old_status = existing["status"]
    cur.execute("UPDATE candidates SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (s.status, candidate_id))

    detail_text = f'{old_status} → {s.status}'
    if s.note:
        detail_text += f' | {s.note}'
    _log_activity(cur, candidate_id, user["id"], "Статус изменён", detail_text)

    # If status is "Запрос информации" and there's a note, save it as a note too
    if s.status == "Запрос информации" and s.note:
        cur.execute(
            "INSERT INTO notes (candidate_id, author_id, content) VALUES (%s, %s, %s)",
            (candidate_id, user["id"], f"**Запрос информации:**\n{s.note}"),
        )
        _log_activity(cur, candidate_id, user["id"], "Запрос информации", s.note[:100])

    # If status is "Тестовое задание" and there's a note, create test assignment
    if s.status == "Тестовое задание" and s.note:
        cur.execute(
            "INSERT INTO test_assignments (candidate_id, description, status, created_by) VALUES (%s, %s, %s, %s)",
            (candidate_id, s.note, "Выдано", user["id"]),
        )
        _log_activity(cur, candidate_id, user["id"], "Тестовое задание создано", s.note[:100])

    _notify_status_change(cur, existing, old_status, s.status, user, note=s.note)

    conn.commit()
    cur.execute("SELECT * FROM candidates WHERE id = %s", (candidate_id,))
    row = cur.fetchone()
    result = _candidate_dict(row, cur)
    conn.close()
    return result


@router.delete("/{candidate_id}")
def delete_candidate(candidate_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM candidates WHERE id = %s", (candidate_id,))
    existing = cur.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404, "Кандидат не найден")
    cur.execute("DELETE FROM candidates WHERE id = %s", (candidate_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/{candidate_id}/timeline")
def get_timeline(candidate_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT a.*, u.display_name as author_name
           FROM activity_log a JOIN users u ON a.user_id = u.id
           WHERE a.candidate_id = %s
           ORDER BY a.created_at DESC""",
        (candidate_id,),
    )
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["created_at"] = str(d["created_at"])
        result.append(d)
    return result
