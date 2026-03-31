from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.auth import get_current_user
from backend.database import get_db

router = APIRouter(prefix="/api/candidates/{candidate_id}/ratings", tags=["ratings"])


class RatingCreate(BaseModel):
    score: int


@router.get("")
def list_ratings(candidate_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute(
        """SELECT r.*, u.display_name
           FROM ratings r JOIN users u ON r.user_id = u.id
           WHERE r.candidate_id = ?""",
        (candidate_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("")
def set_rating(candidate_id: int, r: RatingCreate, user: dict = Depends(get_current_user)):
    if r.score < 1 or r.score > 5:
        raise HTTPException(400, "Оценка должна быть от 1 до 5")
    db = get_db()
    existing = db.execute(
        "SELECT * FROM ratings WHERE candidate_id = ? AND user_id = ?",
        (candidate_id, user["id"]),
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE ratings SET score = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (r.score, existing["id"]),
        )
    else:
        db.execute(
            "INSERT INTO ratings (candidate_id, user_id, score) VALUES (?, ?, ?)",
            (candidate_id, user["id"], r.score),
        )
    db.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (?, ?, ?, ?)",
        (candidate_id, user["id"], "Оценка обновлена", f"Оценка: {r.score}/5"),
    )
    db.commit()
    row = db.execute(
        """SELECT r.*, u.display_name
           FROM ratings r JOIN users u ON r.user_id = u.id
           WHERE r.candidate_id = ? AND r.user_id = ?""",
        (candidate_id, user["id"]),
    ).fetchone()
    db.close()
    return dict(row)
