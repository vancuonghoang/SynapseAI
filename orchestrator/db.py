import sqlite3
import json
from typing import List, Dict, Any, Optional

DB_FILE = "agent_framework/dev.db"

def get_db_connection() -> sqlite3.Connection:
    """Creates and returns a DB connection, with foreign keys enabled and row_factory set."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _parse_row(row: sqlite3.Row) -> Optional[Dict[str, Any]]:
    """Helper to convert sqlite3.Row to a dict and parse JSON fields."""
    if not row:
        return None
    row_dict = dict(row)
    for key in ["dependencies", "acceptance", "meta"]:
        if key in row_dict and isinstance(row_dict[key], str):
            try:
                row_dict[key] = json.loads(row_dict[key])
            except (json.JSONDecodeError, TypeError):
                row_dict[key] = [] if key != 'meta' else {}
    return row_dict

# --- User Stories CRUD --- #

def get_story_by_id(story_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_stories WHERE id = ?", (story_id,))
        return _parse_row(cursor.fetchone())

def get_all_stories() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_stories ORDER BY id")
        rows = cursor.fetchall()
        return [_parse_row(row) for row in rows if row]

def _fetch_current_version(cursor, table: str, record_id: str) -> int:
    cursor.execute(f"SELECT version FROM {table} WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"{table} record '{record_id}' not found.")
    return int(row["version"])

def update_story_status(story_id: str, status: str, expected_version: Optional[int] = None) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        current_version = _fetch_current_version(cursor, "user_stories", story_id)
        compare_version = expected_version if expected_version is not None else current_version
        cursor.execute(
            "UPDATE user_stories SET status = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND version = ?",
            (status, story_id, compare_version)
        )
        if cursor.rowcount == 0:
            raise RuntimeError(f"Optimistic locking failure when updating story '{story_id}'.")
        conn.commit()
        new_version = compare_version + 1
        print(f"[DB] Updated story '{story_id}' to status '{status}' (version {new_version}).")
        return new_version

def update_story_room_doc(story_id: str, room_doc_path: str, expected_version: Optional[int] = None) -> int:
    """Updates the room_doc_path for a given user story."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        current_version = _fetch_current_version(cursor, "user_stories", story_id)
        compare_version = expected_version if expected_version is not None else current_version
        cursor.execute(
            "UPDATE user_stories SET room_doc_path = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND version = ?",
            (room_doc_path, story_id, compare_version)
        )
        if cursor.rowcount == 0:
            raise RuntimeError(f"Optimistic locking failure when updating room doc for story '{story_id}'.")
        conn.commit()
        new_version = compare_version + 1
        print(f"[DB] Set room_doc_path for story '{story_id}' to '{room_doc_path}' (version {new_version}).")
        return new_version

# --- Tasks CRUD --- #

def create_tasks(tasks: List[Dict[str, Any]]):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """INSERT INTO tasks (id, story_id, kind, description, assignee_role, estimate, dependencies, acceptance, status)
               VALUES (:id, :story_id, :kind, :description, :assignee_role, :estimate, :dependencies, :acceptance, :status)""",
            [
                {
                    **task,
                    "estimate": task.get("estimate", "M"),
                    "dependencies": json.dumps(task.get("dependencies", [])),
                    "acceptance": json.dumps(task.get("acceptance", [])),
                }
                for task in tasks
            ]
        )
        conn.commit()
        print(f"[DB] Inserted {len(tasks)} new tasks.")

def get_tasks_for_story(story_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE story_id = ? ORDER BY id", (story_id,))
        rows = cursor.fetchall()
        return [_parse_row(row) for row in rows if row]


def update_task_status(task_id: str, status: str, expected_version: Optional[int] = None) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        current_version = _fetch_current_version(cursor, "tasks", task_id)
        compare_version = expected_version if expected_version is not None else current_version
        cursor.execute(
            "UPDATE tasks SET status = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND version = ?",
            (status, task_id, compare_version)
        )
        if cursor.rowcount == 0:
            raise RuntimeError(f"Optimistic locking failure when updating task '{task_id}'.")
        conn.commit()
        new_version = compare_version + 1
        print(f"[DB] Updated task '{task_id}' to status '{status}' (version {new_version}).")
        return new_version

# --- Logging and Artifacts --- #

def create_log_entry(story_id: str, task_id: str, role: str, level: str, message: str, meta: Optional[Dict] = None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs (story_id, task_id, role, level, message, meta) VALUES (?, ?, ?, ?, ?, ?)",
            (story_id, task_id, role, level, message, json.dumps(meta or {}))
        )
        conn.commit()

def create_artifact(story_id: str, task_id: str, path: str, kind: str, meta: Optional[Dict] = None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO artifacts (story_id, task_id, path, kind, meta) VALUES (?, ?, ?, ?, ?)",
            (story_id, task_id, path, kind, json.dumps(meta or {}))
        )
        conn.commit()
        print(f"[DB] Registered artifact '{path}' for task '{task_id}'.")


def get_logs(limit: Optional[int] = None, since: Optional[str] = None, story_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM logs"
        clauses = []
        params: List[Any] = []

        if story_id:
            clauses.append("story_id = ?")
            params.append(story_id)
        if since:
            clauses.append("ts >= ?")
            params.append(since)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        query += " ORDER BY ts DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        return [_parse_row(row) for row in rows if row]

def get_artifacts_for_story(story_id: str) -> List[Dict[str, Any]]:
    """Retrieves all artifacts associated with a given story_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM artifacts WHERE story_id = ? ORDER BY ts", (story_id,))
        rows = cursor.fetchall()
        return [_parse_row(row) for row in rows if row]
