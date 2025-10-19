from abc import ABC, abstractmethod
from typing import Dict, Any
import json
from pathlib import Path
from datetime import datetime

from agent_framework.orchestrator.ctb import CTB
from agent_framework.orchestrator.db import create_log_entry

class Agent(ABC):
    """Base class for all agents in the system."""
    ROLE = "BASE"

    def __init__(self, llm):
        self.llm = llm

    def _log(self, ctb: CTB, level: str, msg: str, meta: Dict[str, Any] = None):
        """Logs a message to both the database and the story's Room Doc."""
        # 1. Log to database (existing functionality)
        create_log_entry(ctb.story_id, ctb.task_id, self.ROLE, level, msg, meta)

        # 2. Append log to the Room Doc
        try:
            room_doc_path = f"agent_framework/docs/US-{ctb.story_id}.md"
            # Ensure the path is within the allowed guard paths for safety, though it should be.
            # This is a conceptual check; actual guard is in file write operations.
            
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            log_header = f"\n---\n`{timestamp}` | **{self.ROLE} Agent** | Task: `{ctb.task_id}` | Status: `{level}`\n"
            
            log_content = f"> {msg.replace('\n', '\n> ')}\n"

            if meta:
                meta_str = json.dumps(meta, indent=2)
                log_content += f"\n```json\n{meta_str}\n```\n"

            with open(room_doc_path, "a") as f:
                f.write(log_header + log_content)

        except Exception as e:
            # If logging to file fails, we don't want to crash the agent.
            # Log this failure to the primary DB log.
            error_msg = f"Failed to write log to Room Doc: {e}"
            create_log_entry(ctb.story_id, ctb.task_id, self.ROLE, "ERROR", error_msg)
            print(f"[ERROR] {error_msg}")

    @abstractmethod
    async def run(self, ctb: CTB) -> Dict[str, Any]:
        """The main entry point for the agent to perform its task."""
        pass