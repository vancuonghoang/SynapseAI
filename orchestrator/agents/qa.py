from typing import Dict, Any
from pathlib import Path
import json
import subprocess

from orchestrator.agents.base import Agent
from orchestrator.ctb import CTB
from orchestrator.guard import ensure_guarded_write

class QAAgent(Agent):
    """QA Agent: Generates and runs tests to ensure code quality."""
    ROLE = "QA"

    def __init__(self, llm):
        super().__init__(llm)

    async def run(self, ctb: CTB) -> Dict[str, Any]:
        self._log(ctb, "INFO", f"Starting QA task: {ctb.objective}")

        # 1. Generate test code via LLM
        # For this simulation, we assume the objective is to test a previous artifact.
        # A real implementation would need to retrieve the code to be tested.
        try:
            with open(f"agent_framework/orchestrator/prompts/{self.ROLE.lower()}.system.txt", "r") as f:
                system_prompt = f.read()
        except FileNotFoundError:
            system_prompt = "You are a QA Agent. Your goal is to generate and run tests."

        acceptance_lines = "\n- ".join(ctb.acceptance) if ctb.acceptance else "(No acceptance criteria provided)"
        user_prompt = (
            f"Your task is to generate python pytest code for a test file named 'workspace/tests/test_{ctb.story_id.lower()}.py'.\n\n"
            "The tests must verify that the functionality described in the objective has been met according to the following acceptance criteria.\n\n"
            "### Original Task Objective ###\n"
            f"{ctb.objective}\n\n"
            "### MANDATORY Acceptance Criteria to Verify ###\n"
            f"- {acceptance_lines}\n\n"
            "Generate a complete, runnable pytest file. Do not include any explanatory text outside of the code itself."
        )

        self._log(ctb, "INFO", "Calling LLM to generate test cases.")
        test_code_content = await self.llm.complete(
            role=self.ROLE,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            task_id=ctb.task_id,
            story_id=ctb.story_id
        )

        # 2. Write the generated test file safely
        try:
            test_file_path = f"workspace/tests/test_{ctb.story_id.lower()}.py"
            guarded_path = ensure_guarded_write(
                guard_patterns=ctb.guard_paths, root=".", write_path=test_file_path
            )
            Path(guarded_path).parent.mkdir(parents=True, exist_ok=True)
            Path(guarded_path).write_text(test_code_content)
            self._log(ctb, "INFO", "Test file artifact created.", meta={"path": str(guarded_path)})
        except Exception as e:
            self._log(ctb, "ERROR", f"Failed to write test file: {e}")
            return {"status": "Failed", "error": f"Failed to write test file: {e}"}

        # 3. Run the test script
        self._log(ctb, "INFO", "Executing test script: tools/run_tests.sh")
        try:
            process = subprocess.run(
                ["bash", "agent_framework/tools/run_tests.sh"],
                capture_output=True, text=True, check=False, timeout=60
            )
            passed = (process.returncode == 0)
            status = "Done" if passed else "QA Failed"
            self._log(ctb, "INFO" if passed else "ERROR", "Test run completed.", meta={
                "passed": passed,
                "stdout": process.stdout[-2000:],
                "stderr": process.stderr[-2000:]
            })
            
            # 4. Return result with feedback if failed
            feedback = None
            if not passed:
                feedback = f"Tests failed with the following error:\n{process.stderr}"

            return {"status": status, "artifacts": [str(guarded_path)], "feedback": feedback}
        except subprocess.TimeoutExpired:
            self._log(ctb, "ERROR", "Test run timed out.")
            return {"status": "Failed", "error": "Test run timed out."}
        except Exception as e:
            self._log(ctb, "ERROR", f"An unexpected error occurred while running tests: {e}")
            return {"status": "Failed", "error": f"Test execution error: {e}"}
