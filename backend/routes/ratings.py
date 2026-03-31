from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.auth import get_current_user
from backend.database import get_db

router = APIRouter(prefix="/api/candidates/{candidate_id}/ratings", tags=["ratings"])


class RatingCreate(BaseModel):
    score: int


@router.get("")
def list_ratings(candidate_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT r.*, u.display_name
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
