from typing import Dict, Any
from pathlib import Path
import subprocess

from agent_framework.orchestrator.agents.base import Agent
from agent_framework.orchestrator.ctb import CTB
from agent_framework.orchestrator.guard import ensure_guarded_write
from agent_framework.orchestrator.db import create_artifact

class FEAgent(Agent):
    """Frontend Agent: Implements UI components based on specifications."""
    ROLE = "FE"

    def __init__(self, llm):
        super().__init__(llm)

    async def run(self, ctb: CTB) -> Dict[str, Any]:
        self._log(ctb, "INFO", f"Starting frontend task: {ctb.objective}")

        # Define a logical file path for the component
        target_file_path = f"workspace/src/components/{ctb.story_id.lower()}_dashboard.tsx"

        try:
            with open(f"agent_framework/orchestrator/prompts/{self.ROLE.lower()}.system.txt", "r") as f:
                system_prompt = f.read()
        except FileNotFoundError:
            self._log(ctb, "WARN", f"{self.ROLE.lower()}.system.txt not found. Using fallback prompt.")
            system_prompt = "You are a Frontend Agent. Your goal is to implement UI components."

        user_prompt = (
            f"""Please generate the React/TypeScript code for the file '{target_file_path}'.

"""
            f"""### OBJECTIVE ###
{ctb.objective}

"""
            f"""### CONSTRAINTS ###
{ctb.constraints}

"""
            f"""### ACCEPTANCE CRITERIA ###
- {"\n- ".join(ctb.acceptance)}

"""
            f"""Generate a complete, runnable React component file. Do not include any explanatory text."""
        )

        self._log(ctb, "INFO", f"Calling LLM to generate code for '{target_file_path}'.")
        code_content = await self.llm.complete(
            role=self.ROLE,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            task_id=ctb.task_id,
            story_id=ctb.story_id
        )

        try:
            guarded_path = ensure_guarded_write(
                guard_patterns=ctb.guard_paths, root=".", write_path=target_file_path
            )
            Path(guarded_path).parent.mkdir(parents=True, exist_ok=True)
            Path(guarded_path).write_text(code_content)
            self._log(ctb, "INFO", "Successfully wrote code artifact.", meta={"path": str(guarded_path)})

            # Run quality checks
            scripts = ["install_deps.sh", "run_lint.sh", "run_typecheck.sh", "run_tests.sh"]
            for script in scripts:
                self._log(ctb, "INFO", f"Running quality script: {script}")
                process = subprocess.run(
                    ["bash", f"agent_framework/tools/{script}"],
                    capture_output=True, text=True, check=False, timeout=120
                )
                if process.returncode != 0:
                    # run_tests.sh might exit 1 if no runner is configured, which is not a failure.
                    if script == 'run_tests.sh' and "No test runner configured" in process.stdout:
                        self._log(ctb, "WARN", "Tests skipped: No test runner configured.")
                        continue
                    error_details = f"{script} failed.\nSTDOUT:\n{process.stdout}\nSTDERR:\n{process.stderr}"
                    self._log(ctb, "ERROR", error_details)
                    raise Exception(error_details)
                self._log(ctb, "INFO", f"{script} passed.")

            self._log(ctb, "INFO", "All quality checks passed.")

            create_artifact(ctb.story_id, ctb.task_id, str(guarded_path), "code")

            return {"status": "Coding Complete", "artifacts": [str(guarded_path)]}
        except Exception as e:
            self._log(ctb, "ERROR", f"Error during code writing or quality check: {e}")
            return {"status": "Failed", "error": str(e)}
