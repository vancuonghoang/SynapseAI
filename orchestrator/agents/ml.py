from typing import Dict, Any
from pathlib import Path
import glob
import json

from orchestrator.agents.base import Agent
from orchestrator.ctb import CTB
from orchestrator.guard import ensure_guarded_write

class MLAgent(Agent):
    """ML-Quant Agent: Responsible for retrieval and context building tasks."""
    ROLE = "ML"

    def __init__(self, llm):
        super().__init__(llm)

    async def run(self, ctb: CTB) -> Dict[str, Any]:
        self._log(ctb, "INFO", f"Starting ML task: {ctb.objective}")

        # Load system prompt (for policy/constraints alignment)
        try:
            with open("agent_framework/orchestrator/prompts/ml.system.txt", "r") as f:
                system_prompt = f.read()
        except FileNotFoundError:
            system_prompt = "You are the ML Agent. Perform fast retrieval and context building; do not train heavy models."
        # Build a small user prompt to describe retrieval scope (for logging/traceability)
        user_prompt = (
            f"Task Objective: {ctb.objective}\n\n"
            f"Constraints: fast, deterministic, no heavy training. Guard paths: {ctb.guard_paths}.\n\n"
            f"Attachments provided (truncated): AGENTS.MD[{len(ctb.attachments.get('AGENTS.MD',''))} chars],"
            f" BACKLOG.md[{len(ctb.attachments.get('BACKLOG.md',''))} chars], ROOM.md[{len(ctb.attachments.get('ROOM.md',''))} chars]."
        )
        self._log(ctb, "INFO", "ML system/user prompt loaded.", meta={"system_len": len(system_prompt), "user_prompt": user_prompt[:200]})

        # Pattern: Heuristic Retriever
        # This agent finds relevant files to provide context to other agents.
        if "retriever" not in ctb.objective.lower():
            msg = "This ML agent currently only supports 'retriever' tasks."
            self._log(ctb, "WARN", msg)
            return {"status": "Done", "message": msg} # Not a failure, just no-op

        try:
            workspace_path = "workspace"
            search_patterns = [
                f"{workspace_path}/src/**/*.py",
                f"{workspace_path}/src/**/*.ts",
                f"{workspace_path}/tests/**/*.py"
            ]
            
            retrieved_files = []
            for pattern in search_patterns:
                retrieved_files.extend(glob.glob(pattern, recursive=True))
            
            self._log(ctb, "INFO", f"Retrieved {len(retrieved_files)} files.")

            # Create a JSON report as an artifact
            report = {
                "task_id": ctb.task_id,
                "objective": ctb.objective,
                "retrieved_file_count": len(retrieved_files),
                "retrieved_files": retrieved_files[:100] # Limit for brevity
            }

            # Define and guard the artifact path
            artifact_path = f"workspace/artifacts/{ctb.task_id}_retrieval_report.json"
            guarded_path = ensure_guarded_write(
                guard_patterns=ctb.guard_paths,
                root=".",
                write_path=artifact_path
            )

            Path(guarded_path).parent.mkdir(parents=True, exist_ok=True)
            Path(guarded_path).write_text(json.dumps(report, indent=2))

            self._log(ctb, "INFO", "Successfully wrote retrieval report artifact.", meta={"path": str(guarded_path)})

            return {"status": "Done", "artifacts": [str(guarded_path)]}
        except Exception as e:
            self._log(ctb, "ERROR", f"An error occurred during file retrieval: {e}")
            return {"status": "Failed", "error": str(e)}
