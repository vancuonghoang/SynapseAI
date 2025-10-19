from typing import Dict, Any
from pathlib import Path
import glob
import json

from agent_framework.orchestrator.agents.base import Agent
from agent_framework.orchestrator.ctb import CTB
from agent_framework.orchestrator.guard import ensure_guarded_write

class MLAgent(Agent):
    """ML-Quant Agent: Responsible for retrieval and context building tasks."""
    ROLE = "ML"

    def __init__(self, llm):
        super().__init__(llm)

    async def run(self, ctb: CTB) -> Dict[str, Any]:
        self._log(ctb, "INFO", f"Starting ML task: {ctb.objective}")

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
