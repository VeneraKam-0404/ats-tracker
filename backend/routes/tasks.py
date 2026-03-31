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
    db = get_db()
    rows = db.execute(
        """SELECT t.*, u.display_name as creator_name
           FROM test_assignments t JOIN users u ON t.created_by = u.id
           WHERE t.candidate_id = ?
           ORDER BY t.assigned_at DESC""",
        (candidate_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("")
def create_task(candidate_id: int, t: TaskCreate, user: dict = Depends(get_current_user)):
    db = get_db()
    cur = db.execute(
        """INSERT INTO test_assignments (candidate_id, description, status, created_by)
           VALUES (?, ?, ?, ?)""",
        (candidate_id, t.description, t.status, user["id"]),
    )
    db.execute(
        "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (?, ?, ?, ?)",
        (candidate_id, user["id"], "Тестовое задание создано", t.description[:100]),
    )
    db.commit()
    row = db.execute(
        """SELECT t.*, u.display_name as creator_name
           FROM test_assignments t JOIN users u ON t.created_by = u.id WHERE t.id = ?""",
        (cur.lastrowid,),
    ).fetchone()
    db.close()
    return dict(row)


@router.put("/{task_id}")
def update_task(candidate_id: int, task_id: int, t: TaskUpdate, user: dict = Depends(get_current_user)):
    db = get_db()
    existing = db.execute("SELECT * FROM test_assignments WHERE id = ? AND candidate_id = ?",
                          (task_id, candidate_id)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "Задание не найдено")

    updates = {k: v for k, v in t.model_dump().items() if v is not None}
    if t.status and t.status not in VALID_TASK_STATUSES:
        raise HTTPException(400, "Недопустимый статус задания")

    if "status" in updates:
        if updates["status"] == "Получено":
            updates["received_at"] = "CURRENT_TIMESTAMP"
        elif updates["status"] == "Проверено":
            updates["reviewed_at"] = "CURRENT_TIMESTAMP"

    if updates:
        set_parts = []
        values = []
        for k, v in updates.items():
            if v == "CURRENT_TIMESTAMP":
                set_parts.append(f"{k} = CURRENT_TIMESTAMP")
            else:
                set_parts.append(f"{k} = ?")
                values.append(v)
        set_clause = ", ".join(set_parts)
        values += [task_id, candidate_id]
        db.execute(f"UPDATE test_assignments SET {set_clause} WHERE id = ? AND candidate_id = ?", values)

        if "status" in updates:
            db.execute(
                "INSERT INTO activity_log (candidate_id, user_id, action, details) VALUES (?, ?, ?, ?)",
                (candidate_id, user["id"], "Тестовое задание обновлено",
                 f'Статус: {updates["status"]}'),
            )
        db.commit()

    row = db.execute(
        """SELECT t.*, u.display_name as creator_name
           FROM test_assignments t JOIN users u ON t.created_by = u.id WHERE t.id = ?""",
        (task_id,),
    ).fetchone()
    db.close()
    return dict(row)


@router.delete("/{task_id}")
def delete_task(candidate_id: int, task_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("DELETE FROM test_assignments WHERE id = ? AND candidate_id = ?", (task_id, candidate_id))
    db.commit()
    db.close()
    return {"ok": True}
