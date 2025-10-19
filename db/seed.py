import sqlite3
import os
import json

DB_FILE = "agent_framework/dev.db"
SCHEMA_FILE = "agent_framework/db/schema.sql"

# Dữ liệu backlog ban đầu từ plan.md
INITIAL_STORIES = [
    ("A1", "Dev stack & scripts", "DevOps"),
    ("B1", "CTB Builder & role router", "PM/BE"),
    ("C1", "LangGraph Orchestrator", "BE"),
    ("D1", "Retriever", "ML"),
    ("E1", "QA test harness", "QA"),
    ("F1", "Mirror Renderer DB->Markdown", "DevOps"),
    ("G1", "FE Dashboard", "FE"),
    ("H1", "ADR/KD cycle", "PM/Reviewer"),
]

# Kế hoạch task mô phỏng thực tế cho G1, thể hiện sự phân rã của PM
G1_TASKS = [
    (
        "G1.T01", "G1", "impl",
        "Set up the initial Vite project structure for the frontend dashboard.",
        "DevOps", "S", json.dumps([]),
        json.dumps(["Vite project is initialized in workspace/ folder", "package.json contains necessary dependencies"])
    ),
    (
        "G1.T02", "G1", "impl",
        "Create a mock API endpoint in the backend to serve dashboard data.",
        "BE", "M", json.dumps(["G1.T01"]),
        json.dumps(["Endpoint /api/dashboard/status returns a mock JSON response", "Endpoint is documented in OpenAPI spec"])
    ),
    (
        "G1.T03", "G1", "impl",
        "Implement the main Dashboard UI component to display story and task status.",
        "FE", "M", json.dumps(["G1.T02"]),
        json.dumps(["Component fetches and displays data from the mock API", "UI is responsive and follows basic design principles"])
    ),
    (
        "G1.T04", "G1", "test",
        "Write Playwright E2E tests for the dashboard.",
        "QA", "S", json.dumps(["G1.T03"]),
        json.dumps(["Tests cover the main user flow of viewing the dashboard", "Test script runs successfully via tools/run_tests.sh"])
    )
]


def main():
    """Khởi tạo database: tạo schema và điền dữ liệu backlog ban đầu."""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Removed old database file: {DB_FILE}")

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        print(f"Successfully connected to database: {DB_FILE}")

        with open(SCHEMA_FILE, "r") as f:
            schema_sql = f.read()
        cursor.executescript(schema_sql)
        print("Database schema created successfully.")

        print("Seeding initial user stories...")
        for story_id, title, epic in INITIAL_STORIES:
            cursor.execute(
                "INSERT INTO user_stories (id, title, epic, status) VALUES (?, ?, ?, ?)",
                (story_id, title, epic, 'To Do')
            )
        print(f"Seeded {len(INITIAL_STORIES)} user stories.")

        print("Seeding realistic tasks for story G1...")
        for task_data in G1_TASKS:
            cursor.execute(
                "INSERT INTO tasks (id, story_id, kind, description, assignee_role, estimate, dependencies, acceptance, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'To Do')",
                task_data
            )
        print(f"Seeded {len(G1_TASKS)} tasks for story G1.")

        conn.commit()
        conn.close()
        print("Database seeded and connection closed.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
