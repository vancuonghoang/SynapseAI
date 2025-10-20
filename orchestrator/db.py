import os
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text, Engine

DB_FILE = "agent_framework/dev.db"

_engine: Optional[Engine] = None

def get_engine() -> Engine:
    """Initializes and returns a singleton SQLAlchemy Engine."""
    global _engine
    if _engine is None:
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            # Use PostgreSQL in Docker
            print("[DB] Connecting to PostgreSQL via DATABASE_URL...")
            _engine = create_engine(db_url)
        else:
            # Fallback to SQLite for local development
            print(f"[DB] DATABASE_URL not found. Falling back to SQLite at {DB_FILE}...")
            os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
            _engine = create_engine(f"sqlite:///{DB_FILE}")
    return _engine

def get_db_connection(): # This is now a context manager
    """Provides a database connection from the engine."""
    engine = get_engine()
    return engine.connect()

def _parse_row(row) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    row_dict = dict(row._mapping)
    for key in ["dependencies", "acceptance", "meta"]:
        if key in row_dict and isinstance(row_dict[key], str):
            try:
                row_dict[key] = json.loads(row_dict[key])
            except (json.JSONDecodeError, TypeError):
                row_dict[key] = [] if key != 'meta' else {}
    return row_dict

# --- All CRUD functions refactored for SQLAlchemy ---

def get_story_by_id(story_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        result = conn.execute(text("SELECT * FROM user_stories WHERE id = :id"), {"id": story_id})
        return _parse_row(result.fetchone())

def get_all_stories() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        result = conn.execute(text("SELECT * FROM user_stories ORDER BY id"))
        rows = result.fetchall()
        return [_parse_row(row) for row in rows if row]

def update_story_status(story_id: str, status: str):
    with get_db_connection() as conn:
        conn.execute(text("UPDATE user_stories SET status = :status WHERE id = :id"), {"status": status, "id": story_id})
        conn.commit()
        print(f"[DB] Updated story '{story_id}' to status '{status}'.")

def update_story_room_doc(story_id: str, room_doc_path: str):
    with get_db_connection() as conn:
        conn.execute(text("UPDATE user_stories SET room_doc_path = :path WHERE id = :id"), {"path": room_doc_path, "id": story_id})
        conn.commit()
        print(f"[DB] Set room_doc_path for story '{story_id}'.")

def create_tasks(tasks: List[Dict[str, Any]]):
    with get_db_connection() as conn:
        # SQLAlchemy's text() handles parameterization safely
        stmt = text("""INSERT INTO tasks (id, story_id, kind, description, assignee_role, estimate, dependencies, acceptance, status)
               VALUES (:id, :story_id, :kind, :description, :assignee_role, :estimate, :dependencies, :acceptance, :status)""")
        task_dicts = [
            {
                **task,
                "estimate": task.get("estimate", "M"),
                "dependencies": json.dumps(task.get("dependencies", [])),
                "acceptance": json.dumps(task.get("acceptance", [])),
            }
            for task in tasks
        ]
        conn.execute(stmt, task_dicts)
        conn.commit()
        print(f"[DB] Inserted {len(tasks)} new tasks.")

def get_tasks_for_story(story_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        result = conn.execute(text("SELECT * FROM tasks WHERE story_id = :id ORDER BY id"), {"id": story_id})
        rows = result.fetchall()
        return [_parse_row(row) for row in rows if row]

def update_task_status(task_id: str, status: str):
    with get_db_connection() as conn:
        conn.execute(text("UPDATE tasks SET status = :status WHERE id = :id"), {"status": status, "id": task_id})
        conn.commit()
        print(f"[DB] Updated task '{task_id}' to status '{status}'.")

def create_log_entry(story_id: str, task_id: str, role: str, level: str, message: str, meta: Optional[Dict] = None):
    with get_db_connection() as conn:
        conn.execute(
            text("INSERT INTO logs (story_id, task_id, role, level, message, meta) VALUES (:sid, :tid, :role, :level, :msg, :meta)"),
            {"sid": story_id, "tid": task_id, "role": role, "level": level, "msg": message, "meta": json.dumps(meta or {})}
        )
        conn.commit()

def create_artifact(story_id: str, task_id: str, path: str, kind: str, meta: Optional[Dict] = None):
    with get_db_connection() as conn:
        conn.execute(
            text("INSERT INTO artifacts (story_id, task_id, path, kind, meta) VALUES (:sid, :tid, :path, :kind, :meta)"),
            {"sid": story_id, "tid": task_id, "path": path, "kind": kind, "meta": json.dumps(meta or {})}
        )
        conn.commit()
        print(f"[DB] Registered artifact '{path}' for task '{task_id}'.")

def get_artifacts_for_story(story_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        result = conn.execute(text("SELECT * FROM artifacts WHERE story_id = :id ORDER BY ts"), {"id": story_id})
        rows = result.fetchall()
        return [_parse_row(row) for row in rows if row]