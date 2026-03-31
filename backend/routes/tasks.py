from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.auth import get_current_user
from backend.database import get_db

router = APIRouter(prefix="/api/candidates/{candidate_id}/tasks", tags=["test_assignments"])

VALID_TASK_STATUSES = ["Выдано", "Получено", "Проверено"]


class TaskCreate(BaseModel):
    description: str = ""
    status: str = "Выдано"


class TaskUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None
    rating: Optional[int] = None
    comment: Optional[str] = None


@router.get("")
def list_tasks(candidate_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT t.*, u.display_name as creator_name
           FROM test_assignments t JOIN users u ON t.created_by = u.id
           WHERE t.candidate_id = %s
           ORDER BY t.assigned_at DESC""",
        (candidate_id,),
    )
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        for k in ("assigned_at", "received_at", "reviewed_at"):
            if d.get(k):
                d[k] = str(d[k])
        result.append(d)
    return result


@router.post("")
def create_task(candidate_id: int, t: TaskCreate, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO test_assignments (candidate_id, description, status, created_by)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (candidate_id, t.description, t.status, user["id"]),
    )
    tid = cur.fetchone()["id"]
    cur.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
        (candidate_id, user["id"], "Тестовое задание создано", t.description[:100]),
    )
    conn.commit()
    cur.execute(
        """SELECT t.*, u.display_name as creator_name
           FROM test_assignments t JOIN users u ON t.created_by = u.id WHERE t.id = %s""",
        (tid,),
    )
    row = cur.fetchone()
    conn.close()
    d = dict(row)
    for k in ("assigned_at", "received_at", "reviewed_at"):
        if d.get(k):
            d[k] = str(d[k])
    return d


@router.put("/{task_id}")
def update_task(candidate_id: int, task_id: int, t: TaskUpdate, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM test_assignments WHERE id = %s AND candidate_id = %s",
                (task_id, candidate_id))
    existing = cur.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404, "Задание не найдено")

    updates = {k: v for k, v in t.model_dump().items() if v is not None}
    if t.status and t.status not in VALID_TASK_STATUSES:
        raise HTTPException(400, "Недопустимый статус задания")

    timestamp_fields = []
    if "status" in updates:
        if updates["status"] == "Получено":
            timestamp_fields.append("received_at")
        elif updates["status"] == "Проверено":
            timestamp_fields.append("reviewed_at")

    if updates:
        set_parts = []
        values = []
        for k, v in updates.items():
            set_parts.append(f"{k} = %s")
            values.append(v)
        for tf in timestamp_fields:
            set_parts.append(f"{tf} = CURRENT_TIMESTAMP")
        set_clause = ", ".join(set_parts)
        values += [task_id, candidate_id]
        cur.execute(f"UPDATE test_assignments SET {set_clause} WHERE id = %s AND candidate_id = %s", values)

        if "status" in updates:
            cur.execute(
                "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (%s, %s, %s, %s)",
                (candidate_id, user["id"], "Тестовое задание обновлено",
                 f'Статус: {updates["status"]}'),
            )
        conn.commit()

    cur.execute(
        """SELECT t.*, u.display_name as creator_name
           FROM test_assignments t JOIN users u ON t.created_by = u.id WHERE t.id = %s""",
        (task_id,),
    )
    row = cur.fetchone()
    conn.close()
    d = dict(row)
    for k in ("assigned_at", "received_at", "reviewed_at"):
        if d.get(k):
            d[k] = str(d[k])
    return d


@router.delete("/{task_id}")
def delete_task(candidate_id: int, task_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM test_assignments WHERE id = %s AND candidate_id = %s", (task_id, candidate_id))
    conn.commit()
    conn.close()
    return {"ok": True}
