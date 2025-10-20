import sys
import os
from datetime import datetime

# Ensure the parent directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from orchestrator.db import get_all_stories, get_tasks_for_story

BACKLOG_FILE_PATH = "BACKLOG.md"

def main():
    """Fetches all data from the database and renders the BACKLOG.md file."""
    print("Starting backlog renderer...")
    try:
        stories = get_all_stories()
        markdown_content = []

        # --- YAML Front Matter ---
        markdown_content.append("---")
        markdown_content.append(f"source: mirror-from-db")
        markdown_content.append(f"generated_at: {datetime.utcnow().isoformat()}Z")
        markdown_content.append("---")
        markdown_content.append("\n# Project Backlog")
        markdown_content.append("_This file is auto-generated from the database. Do not edit manually._")

        if not stories:
            markdown_content.append("\n*No user stories found in the database.*")
        else:
            for story in stories:
                markdown_content.append(f"\n## US: {story['id']} - {story['title']}")
                markdown_content.append(f"- **Status:** `{story['status']}`")
                markdown_content.append(f"- **Epic:** {story['epic']}")
                
                tasks = get_tasks_for_story(story['id'])
                if not tasks:
                    markdown_content.append("- **Tasks:** None")
                else:
                    markdown_content.append("- **Tasks:**")
                    for task in tasks:
                        markdown_content.append(f"  - **{task['id']}:** {task['description']} (`{task['assignee_role']}` | `{task['status']}`)")
        
        # Write to file
        with open(BACKLOG_FILE_PATH, "w") as f:
            f.write("\n".join(markdown_content))
        
        print(f"Successfully rendered {len(stories)} stories to {BACKLOG_FILE_PATH}")

    except Exception as e:
        print(f"[ERROR] Failed to render backlog: {e}")

if __name__ == "__main__":
    main()
