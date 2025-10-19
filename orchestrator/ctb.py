from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class CTB:
    """Contextual Task Bundle: Gói ngữ cảnh và nhiệm vụ cho mỗi agent."""
    task_id: str
    role: str
    story_id: str
    objective: str
    constraints: List[str]
    attachments: Dict[str, str]  # BACKLOG.md, AGENTS.MD, ROOM.md (content)
    guard_paths: List[str]
    acceptance: List[str]
    llm: Dict[str, Any]
