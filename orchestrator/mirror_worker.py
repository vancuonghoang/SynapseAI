from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

from orchestrator.db import get_all_stories, get_tasks_for_story


def _format_story_section(story: Dict[str, str], tasks: List[Dict[str, str]]) -> List[str]:
    lines: List[str] = []
    header = f"## {story['id']} – {story['title']} [{story['status']}]"
    lines.append(header)
    lines.append(f"- Epic: {story['epic']}")
    if story.get("room_doc_path"):
        lines.append(f"- Room Doc: {story['room_doc_path']}")
    lines.append("")

    if not tasks:
        lines.append("_No tasks recorded._")
        lines.append("")
        return lines

    lines.append("| Task ID | Kind | Assignee | Status | Estimate | Updated | Description |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for task in tasks:
        estimate = task.get("estimate", "")
        updated_at = task.get("updated_at", "")
        description = task.get("description", "").replace("|", "\\|")
        lines.append(
            f"| {task['id']} | {task['kind']} | {task['assignee_role']} | "
            f"{task['status']} | {estimate} | {updated_at} | {description} |"
        )
    lines.append("")
    return lines


def render_backlog(output_path: str = "BACKLOG.md") -> Path:
    """Render BACKLOG.md from the canonical database snapshot."""
    generated_at = datetime.now(timezone.utc).isoformat()
    stories = get_all_stories()

    lines: List[str] = [
        "---",
        "source: mirror-from-db",
        f"generated_at: {generated_at}",
        "---",
        "",
        "# Project Backlog (Mirror)",
        "",
    ]

    for story in stories:
        tasks = get_tasks_for_story(story["id"])
        lines.extend(_format_story_section(story, tasks))

    output_file = Path(output_path)
    output_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Mirror] Backlog rendered at {output_file} ({generated_at})")
    return output_file


def main():
    render_backlog()


if __name__ == "__main__":
    main()
