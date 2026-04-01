from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.auth import get_current_user
from backend.database import get_db

router = APIRouter(prefix="/api/candidates/{candidate_id}/ratings", tags=["ratings"])

VALID_STAGES = ["resume", "test", "interview", "offer"]


class RatingCreate(BaseModel):
    score: int


class StageRatingCreate(BaseModel):
    stage: str
    score: int
    comment: str = ""
    meeting_id: Optional[int] = None


# Legacy: simple overall rating (kept for backward compat)
@router.get("")
def list_ratings(candidate_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT r.*, u.display_name, u.username
           FROM ratings r JOIN users u ON r.user_id = u.id
           WHERE r.candidate_id = %s""",
        (candidate_id,),
    )
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        for k in ("created_at", "updated_at"):
            if d.get(k):
                d[k] = str(d[k])
        result.append(d)
    return result


@router.post("")
def set_rating(candidate_id: int, r: RatingCreate, user: dict = Depends(get_current_user)):
    if r.score < 1 or r.score > 5:
        raise HTTPException(400, "Оценка должна быть от 1 до 5")
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO ratings (candidate_id, user_id, score)
           VALUES (%s, %s, %s)
           ON CONFLICT (candidate_id, user_id) DO UPDATE SET score = %s, updated_at = CURRENT_TIMESTAMP""",
        (candidate_id, user["id"], r.score, r.score),
    )
    cur.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
        (candidate_id, user["id"], "Оценка обновлена", f"Оценка: {r.score}/5"),
    )
    conn.commit()
    cur.execute(
        """SELECT r.*, u.display_name
           FROM ratings r JOIN users u ON r.user_id = u.id
           WHERE r.candidate_id = %s AND r.user_id = %s""",
        (candidate_id, user["id"]),
    )
    row = cur.fetchone()
    conn.close()
    d = dict(row)
    for k in ("created_at", "updated_at"):
        if d.get(k):
            d[k] = str(d[k])
    return d


# === Stage ratings ===

@router.get("/stages")
def list_stage_ratings(candidate_id: int, user: dict = Depends(get_current_user)):
    """Get all stage ratings for a candidate, grouped by stage."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT sr.*, u.display_name, u.username
           FROM stage_ratings sr JOIN users u ON sr.user_id = u.id
           WHERE sr.candidate_id = %s
           ORDER BY sr.created_at ASC""",
        (candidate_id,),
    )
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("created_at"):
            d["created_at"] = str(d["created_at"])
        result.append(d)
    return result


@router.post("/stages")
def set_stage_rating(candidate_id: int, r: StageRatingCreate, user: dict = Depends(get_current_user)):
    if r.stage not in VALID_STAGES:
        raise HTTPException(400, f"Недопустимый этап: {r.stage}")
    if r.score < 1 or r.score > 5:
        raise HTTPException(400, "Оценка должна быть от 1 до 5")

    conn = get_db()
    cur = conn.cursor()

    # For interview stage with meeting_id, allow multiple ratings per meeting
    # For other stages, one rating per user per stage
    meeting_id = r.meeting_id if r.stage == "interview" else None

    cur.execute(
        """INSERT INTO stage_ratings (candidate_id, user_id, stage, score, comment, meeting_id)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (candidate_id, user_id, stage, meeting_id)
           DO UPDATE SET score = %s, comment = %s, created_at = CURRENT_TIMESTAMP""",
        (candidate_id, user["id"], r.stage, r.score, r.comment, meeting_id,
         r.score, r.comment),
    )

    stage_labels = {"resume": "Резюме", "test": "Тестовое", "interview": "Интервью", "offer": "Итоговая"}
    cur.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
        (candidate_id, user["id"], "Оценка этапа",
         f'{stage_labels.get(r.stage, r.stage)}: {r.score}/5' + (f' — {r.comment}' if r.comment else '')),
    )

    # Also update the legacy overall rating with the latest score
    cur.execute(
        """INSERT INTO ratings (candidate_id, user_id, score)
           VALUES (%s, %s, %s)
           ON CONFLICT (candidate_id, user_id) DO UPDATE SET score = %s, updated_at = CURRENT_TIMESTAMP""",
        (candidate_id, user["id"], r.score, r.score),
    )

    conn.commit()
    conn.close()
    return {"ok": True, "stage": r.stage, "score": r.score}
