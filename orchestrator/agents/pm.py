import json
from typing import Dict, Any
from pathlib import Path

from agent_framework.orchestrator.agents.base import Agent
from agent_framework.orchestrator.ctb import CTB
from agent_framework.orchestrator.db import create_tasks, update_story_status, create_artifact
from agent_framework.orchestrator.guard import ensure_guarded_write

class PMAgent(Agent):
    """Project Manager Agent: Decomposes stories, creates specs, and validates plans."""
    ROLE = "PM"

    def __init__(self, llm):
        super().__init__(llm)

    def _validate_plan(self, tasks_data: Any, story_id: str) -> list:
        # ... (validation logic remains the same)
        if not isinstance(tasks_data, list):
            raise ValueError("LLM response is not a JSON list.")
        validated_tasks = []
        seen_ids = set()
        allowed_estimates = {"S", "M", "L"}
        for index, task_item in enumerate(tasks_data):
            if not isinstance(task_item, dict):
                raise ValueError(f"Task item #{index} is not a dictionary.")
            required_keys = ['id', 'description', 'assignee_role', 'kind', 'estimate']
            missing_keys = [key for key in required_keys if key not in task_item]
            if missing_keys:
                raise ValueError(f"Task item #{index} is missing required keys: {missing_keys}")
            task_id = task_item['id']
            if not isinstance(task_id, str) or not task_id.startswith(f"{story_id}."):
                raise ValueError(f"Task id '{task_id}' must be a string starting with '{story_id}'.")
            if task_id in seen_ids:
                raise ValueError(f"Duplicate task id detected: {task_id}")
            seen_ids.add(task_id)
            dependencies = task_item.get('dependencies', [])
            if not isinstance(dependencies, list) or any(not isinstance(dep, str) for dep in dependencies):
                raise ValueError(f"Task '{task_id}' has invalid 'dependencies'; expected a list of strings.")
            acceptance = task_item.get('acceptance', [])
            if not isinstance(acceptance, list) or not acceptance or any(not isinstance(item, str) for item in acceptance):
                raise ValueError(f"Task '{task_id}' must have a non-empty list of string acceptance criteria.")
            if task_item['estimate'] not in allowed_estimates:
                raise ValueError(f"Task '{task_id}' has an invalid estimate. Must be one of {sorted(allowed_estimates)}.")
            task_item['story_id'] = story_id
            task_item['status'] = 'To Do'
            validated_tasks.append(task_item)
        return validated_tasks

    async def run(self, ctb: CTB) -> Dict[str, Any]:
        self._log(ctb, "INFO", f"Starting objective: {ctb.objective}")
        update_story_status(ctb.story_id, "In Progress")

        try:
            with open(f"agent_framework/orchestrator/prompts/{self.ROLE.lower()}.system.txt", "r") as f:
                system_prompt = f.read()
        except FileNotFoundError:
            self._log(ctb, "WARN", "pm.system.txt not found. Using fallback prompt.")
            system_prompt = "You are a PM Agent. Your goal is to plan tasks and write specs."

        # --- Step 1: Generate Task Plan ---
        plan_prompt = (
            f"Analyze the user story and break it down into a JSON list of tasks.\n\n"
            f"USER STORY (ID: {ctb.story_id}): {ctb.objective}\n"
            f"Respond with a valid JSON array of task objects. Each task must have id, kind, description, assignee_role, dependencies, acceptance, and an estimate ('S', 'M', or 'L')."
        )
        self._log(ctb, "INFO", "Calling LLM to generate task plan.")
        # Using a mock for stability, but it goes through validation
        llm_plan_response = f'''
        [
            {{"id": "{ctb.story_id}.T01", "kind": "impl", "description": "Set up the initial Vite project structure.", "assignee_role": "DevOps", "dependencies": [], "acceptance": ["Vite project is initialized"], "estimate": "S"}},
            {{"id": "{ctb.story_id}.T02", "kind": "impl", "description": "Implement the main Dashboard UI component.", "assignee_role": "FE", "dependencies": ["{ctb.story_id}.T01"], "acceptance": ["Component displays mock data"], "estimate": "M"}},
            {{"id": "{ctb.story_id}.T03", "kind": "test", "description": "Write E2E tests for the dashboard.", "assignee_role": "QA", "dependencies": ["{ctb.story_id}.T02"], "acceptance": ["Tests cover the main user flow"], "estimate": "S"}}
        ]
        '''
        try:
            tasks_data = json.loads(llm_plan_response)
            validated_tasks = self._validate_plan(tasks_data, ctb.story_id)
            self._log(ctb, "INFO", f"LLM plan validated successfully with {len(validated_tasks)} tasks.")
            create_tasks(validated_tasks)
            self._log(ctb, "INFO", "Inserted new tasks into database.")
        except (json.JSONDecodeError, ValueError) as e:
            error_message = f"Failed to parse or validate LLM plan: {e}"
            self._log(ctb, "ERROR", error_message, meta={"raw_response": llm_plan_response})
            return {"status": "Failed", "error": error_message}

        # --- Step 2: Generate SPEC for Room Doc ---
        spec_prompt = (
            f"Based on the user story, write a detailed technical specification (SPEC) in Markdown format.\n\n"
            f"USER STORY: {ctb.objective}\n\n"
            f"The SPEC should include sections for: Overview, Key Features, and Acceptance Criteria based on the plan."
        )
        self._log(ctb, "INFO", "Calling LLM to generate SPEC for Room Doc.")
        # Mocking SPEC generation
        spec_content = f"""# SPEC for User Story: {ctb.story_id}\n\n## 1. Overview\n\nThis document outlines the technical specifications for implementing the feature: '{ctb.objective}'.\n\n## 2. Key Features\n\n- A frontend dashboard will be created.\n- It will display the status of stories and tasks.\n- It will provide links to generated artifacts.\n\n## 3. Acceptance Criteria\n\n- The application must be responsive.\n- All generated code must pass linting, type-checking, and testing stages.\n"""
        
        room_doc_path = Path(f"agent_framework/docs/US-{ctb.story_id}.md")
        room_doc_path.parent.mkdir(parents=True, exist_ok=True)
        room_doc_path.write_text(spec_content)
        self._log(ctb, "INFO", "Successfully wrote SPEC to Room Doc.", meta={"path": str(room_doc_path)})
        create_artifact(ctb.story_id, ctb.task_id, str(room_doc_path), "spec")

        return {"status": "Done", "new_tasks_count": len(validated_tasks)}
