-- Lược đồ cho hệ thống Coding Agent, DB là nguồn chân lý.
-- Tương thích với SQLite cho dev và Postgres cho prod.

-- Bảng chứa các User Story chính của dự án
CREATE TABLE IF NOT EXISTS user_stories (
  id TEXT PRIMARY KEY,                -- "A1"
  title TEXT NOT NULL,
  epic TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('To Do','In Progress','QA','Done','Failed')) DEFAULT 'To Do',
  room_doc_path TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Bảng chứa các task con được phân rã từ User Story
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,                -- "A1.T01"
  story_id TEXT NOT NULL REFERENCES user_stories(id),
  kind TEXT NOT NULL,                 -- "spec"|"plan"|"design"|"impl"|"test"|"docs"|"review"|"pr"
  description TEXT NOT NULL,
  assignee_role TEXT NOT NULL,        -- "PM"|"DevOps"|"BE"|"FE"|"ML"|"QA"
  estimate TEXT NOT NULL CHECK (estimate IN ('S','M','L')) DEFAULT 'M',
  status TEXT NOT NULL CHECK (status IN ('To Do','In Progress','Coding Complete','QA Failed','Done')) DEFAULT 'To Do',
  dependencies TEXT NOT NULL DEFAULT '[]', -- JSON array of task IDs
  acceptance TEXT NOT NULL DEFAULT '[]', -- JSON array of acceptance criteria strings
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Bảng ghi lại mọi hoạt động của các agent (audit trail)
CREATE TABLE IF NOT EXISTS logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  story_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  role TEXT NOT NULL,
  level TEXT NOT NULL,                -- "INFO"|"WARN"|"ERROR"
  message TEXT NOT NULL,
  meta TEXT NOT NULL DEFAULT '{}',    -- JSON object for extra data
  ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Bảng lưu lại các file/artifact được tạo ra
CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  story_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  path TEXT NOT NULL,
  hash TEXT,
  kind TEXT NOT NULL,                 -- "spec"|"design"|"code"|"test"|"report"
  meta TEXT NOT NULL DEFAULT '{}',    -- JSON object for extra data
  ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tạo trigger để tự động cập nhật `updated_at` khi một dòng được sửa (hữu ích cho Postgres)
CREATE TRIGGER IF NOT EXISTS update_user_stories_updated_at
AFTER UPDATE ON user_stories
FOR EACH ROW
BEGIN
    UPDATE user_stories SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS update_tasks_updated_at
AFTER UPDATE ON tasks
FOR EACH ROW
BEGIN
    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
