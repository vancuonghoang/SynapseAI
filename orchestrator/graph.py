import asyncio
import os
from typing import TypedDict, List, Dict, Any, Optional, Literal
from langgraph.graph import StateGraph, END
from pathlib import Path

from agent_framework.orchestrator.db import get_tasks_for_story, update_task_status, get_story_by_id, update_story_room_doc
from agent_framework.orchestrator.ctb import CTB
from agent_framework.orchestrator.llm_client import LLMClient, LLMConfig
from agent_framework.orchestrator.agents.pm import PMAgent
from agent_framework.orchestrator.agents.devops import DevOpsAgent
from agent_framework.orchestrator.agents.be import BEAgent
from agent_framework.orchestrator.agents.ml import MLAgent
from agent_framework.orchestrator.agents.qa import QAAgent
from agent_framework.orchestrator.agents.fe import FEAgent

import yaml
from datetime import datetime, timezone

# --- 1. Định nghĩa State của Graph ---
class GraphState(TypedDict):
    story_id: str
    story_objective: str
    tasks: List[Dict[str, Any]]
    current_task_index: int
    feedback_for_dev: Optional[str]
    retries: Dict[str, int]
    next_step: Literal["PLAN", "DEV", "QA", "FINISH"]
    error: bool
    error_message: Optional[str]

# --- 2. Tải cấu hình và Factory ---
def load_role_guards() -> Dict[str, List[str]]:
    """Tải cấu hình guard_paths từ file roles.yaml, xử lý cả dict và list."""
    try:
        with open("agent_framework/config/roles.yaml", "r") as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print("[Warning] config/roles.yaml not found. Using empty guard paths.")
        return {}

    guards: Dict[str, List[str]] = {}
    for role, value in raw.items():
        if isinstance(value, dict):
            guards[role] = list(value.get("guard_paths", []))
        elif isinstance(value, list):
            guards[role] = list(value)
        else:
            guards[role] = []
    return guards

ROLE_GUARDS = load_role_guards()
MAX_RETRIES = 2

def _config_to_llm_config(raw_cfg: Dict[str, Any], default_name: str, default_provider: str) -> LLMConfig:
    cfg = raw_cfg or {}
    return LLMConfig(
        name=cfg.get("name", default_name),
        temperature=float(cfg.get("temperature", 0.2)),
        max_tokens=int(cfg.get("max_tokens", 2000)),
        provider=cfg.get("provider", default_provider)
    )


def build_llm_client() -> LLMClient:
    config_path = Path("agent_framework/config/models.yaml")
    default_provider = "openai"
    role_to_config: Dict[str, LLMConfig] = {}
    overrides: Dict[str, Dict[str, LLMConfig]] = {"tasks": {}, "stories": {}}

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            default_provider = raw.get("default_provider", default_provider)

            for role, cfg in (raw.get("models", {}) or {}).items():
                role_to_config[role] = _config_to_llm_config(cfg, "gpt-4o", default_provider)

            raw_overrides = raw.get("overrides", {}) or {}
            for task_id, cfg in (raw_overrides.get("tasks", {}) or {}).items():
                overrides["tasks"][task_id] = _config_to_llm_config(cfg, "gpt-4o", default_provider)
            for story_id, cfg in (raw_overrides.get("stories", {}) or {}).items():
                overrides["stories"][story_id] = _config_to_llm_config(cfg, "gpt-4o", default_provider)
        except Exception as exc:
            print(f"[LLM Config] Failed to load models.yaml: {exc}. Falling back to defaults.")
            role_to_config = {}
            overrides = {"tasks": {}, "stories": {}}
    else:
        print("[LLM Config] models.yaml not found; using in-code defaults.")

    if not role_to_config:
        # provide sensible defaults if config missing
        role_to_config = {
            "PM": LLMConfig(name="gpt-4o", temperature=0.2, provider=default_provider),
            "DevOps": LLMConfig(name="gpt-4o-mini", temperature=0.2, provider=default_provider),
            "BE": LLMConfig(name="gpt-4o", temperature=0.2, provider=default_provider),
            "ML": LLMConfig(name="gpt-4o", temperature=0.1, provider=default_provider),
            "QA": LLMConfig(name="gpt-4o-mini", temperature=0.1, provider=default_provider),
            "FE": LLMConfig(name="gpt-4o-mini", temperature=0.3, provider=default_provider),
        }

    return LLMClient(default_provider=default_provider, role_to_config=role_to_config, overrides=overrides)

def agent_factory(role: str, llm: LLMClient) -> Any:
    agents = {
        "PM": PMAgent, "DevOps": DevOpsAgent, "BE": BEAgent,
        "ML": MLAgent, "QA": QAAgent, "FE": FEAgent,
    }
    agent_class = agents.get(role)
    if not agent_class: raise ValueError(f"Unknown agent role: {role}")
    return agent_class(llm)

# --- 3. CTB Builder ---
def _build_ctb(task: Dict[str, Any], story: Dict[str, Any], role_override: Optional[str] = None) -> CTB:
    role = role_override or task['assignee_role']
    task_id = f"{task['id']}.{role_override}" if role_override else task['id']
    room_doc_path = story.get('room_doc_path', f"agent_framework/docs/US-{story['id']}.md")
    try:
        attachments = {
            "AGENTS.MD": open("agent_framework/AGENTS.MD").read(),
            "BACKLOG.md": open("agent_framework/BACKLOG.md").read(),
            "ROOM.md": open(room_doc_path).read() if os.path.exists(room_doc_path) else ""
        }
    except FileNotFoundError as e:
        print(f"[Error] Failed to read attachment file: {e}")
        raise
    return CTB(
        task_id=task_id, role=role, story_id=story['id'], objective=task['description'],
        constraints=["Follow AGENTS.MD rules"], attachments=attachments,
        guard_paths=ROLE_GUARDS.get(role, []),
        acceptance=task.get('acceptance', []),
        llm={}
    )


def _append_room_log(room_doc_path: str, role: str, title: str, body_lines: List[str]) -> None:
    if not room_doc_path:
        return
    doc_path = Path(room_doc_path)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = ["", f"### {timestamp} – {role}: {title}", ""]
    lines.extend(body_lines)
    lines.append("")
    with open(doc_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))

# --- 4. Nodes (Sửa lỗi plan_node) ---
async def plan_node(state: GraphState) -> Dict[str, Any]:
    print("\n--- Executing Planning Node ---")
    story_id = state['story_id']
    room_doc_path = f"agent_framework/docs/US-{story_id}.md"
    Path("agent_framework/docs").mkdir(exist_ok=True)
    if not os.path.exists(room_doc_path):
        Path(room_doc_path).write_text(f"# User Story: {story_id}\n\nObjective: {state['story_objective']}\n\n")
        try:
            update_story_room_doc(story_id, room_doc_path)
        except RuntimeError as exc:
            return {"error": True, "error_message": str(exc), "next_step": "FINISH"}
        print(f"Created Room Doc: {room_doc_path}")

    # Tạo CTB đầy đủ cho PMAgent, tuân thủ plan.md
    try:
        attachments = {
            "AGENTS.MD": open("agent_framework/AGENTS.MD").read(),
            "BACKLOG.md": open("agent_framework/BACKLOG.md").read(),
            "ROOM.md": open(room_doc_path).read()
        }
    except FileNotFoundError as e:
        return {"error": True, "error_message": f"Failed to build CTB for PM: {e}", "next_step": "FINISH"}

    ctb = CTB(
        task_id=f"{story_id}.PLAN", role="PM", story_id=story_id,
        objective=state['story_objective'], constraints=["Break down into tasks for DevOps, BE, FE, and QA roles"],
        attachments=attachments, guard_paths=[], acceptance=["Tasks are created in DB"], llm={}
    )

    llm = build_llm_client()
    pm_agent = agent_factory("PM", llm)
    result = await pm_agent.run(ctb)

    if result["status"] == "Failed":
        return {"error": True, "error_message": result.get("error", "Planning failed"), "next_step": "FINISH"}
    
    tasks = get_tasks_for_story(story_id)
    if not tasks:
        return {"error": True, "error_message": f"No tasks found for story {story_id} after planning.", "next_step": "FINISH"}
    summary_lines = [f"- {task['id']} ({task['assignee_role']} – est {task.get('estimate', '?')}): {task['description']}" for task in tasks]
    _append_room_log(room_doc_path, "PM", "Planning completed", summary_lines)

    return {"tasks": tasks, "current_task_index": 0, "next_step": "DEV", "retries": {}}

async def dev_node(state: GraphState) -> Dict[str, Any]:
    task_index = state["current_task_index"]
    task = state["tasks"][task_index]
    print(f"\n--- Executing DEV Node for Task: {task['id']} ({task['assignee_role']}) ---")
    story = get_story_by_id(state['story_id'])
    if not story:
        return {"error": True, "error_message": f"Story {state['story_id']} not found.", "next_step": "FINISH"}
    try:
        ctb = _build_ctb(task, story)
    except FileNotFoundError:
        return {"error": True, "error_message": "Failed to build CTB due to missing attachments.", "next_step": "FINISH"}
    if state.get("feedback_for_dev"):
        ctb.objective += f"\n\n**QA FEEDBACK:** You must fix this issue: {state['feedback_for_dev']}"
        print(f"Retrying task {task['id']} with QA feedback.")
    llm = build_llm_client()
    worker_agent = agent_factory(task['assignee_role'], llm)
    room_doc_path = story.get('room_doc_path', f"agent_framework/docs/US-{story['id']}.md")
    try:
        task['version'] = update_task_status(task['id'], "In Progress", task.get('version'))
    except RuntimeError as exc:
        _append_room_log(room_doc_path, task['assignee_role'], f"Task {task['id']} update failed", [f"- Error: {exc}"])
        return {"error": True, "error_message": str(exc), "next_step": "FINISH"}
    result = await worker_agent.run(ctb)
    final_status = "Coding Complete" if result.get("status") != "Failed" else "Failed"
    try:
        task['version'] = update_task_status(task['id'], final_status, task.get('version'))
    except RuntimeError as exc:
        _append_room_log(room_doc_path, task['assignee_role'], f"Task {task['id']} status sync failed", [f"- Intended status: {final_status}", f"- Error: {exc}"])
        return {"error": True, "error_message": str(exc), "next_step": "FINISH"}

    log_lines = [f"- Objective: {ctb.objective}", f"- Status: {final_status}"]
    artifacts = result.get("artifacts") or []
    if artifacts:
        log_lines.append("- Artifacts:")
        log_lines.extend([f"  - {artifact}" for artifact in artifacts])
    if result.get("error"):
        log_lines.append(f"- Error: {result['error']}")
    _append_room_log(room_doc_path, task['assignee_role'], f"Task {task['id']} execution", log_lines)

    if final_status == "Failed":
        return {"error": True, "error_message": result.get("error", "Dev agent failed to execute."), "next_step": "FINISH"}
    return {"next_step": "QA", "feedback_for_dev": None}

async def qa_node(state: GraphState) -> Dict[str, Any]:
    task_index = state["current_task_index"]
    task = state["tasks"][task_index]
    print(f"\n--- Executing QA Node for Task: {task['id']} ---")
    story = get_story_by_id(state['story_id'])
    if not story:
        return {"error": True, "error_message": f"Story {state['story_id']} not found.", "next_step": "FINISH"}
    try:
        ctb = _build_ctb(task, story, role_override="QA")
    except FileNotFoundError:
        return {"error": True, "error_message": "Failed to build CTB for QA due to missing attachments.", "next_step": "FINISH"}
    llm = build_llm_client()
    qa_agent = agent_factory("QA", llm)
    result = await qa_agent.run(ctb)
    qa_status = result.get("status", "Done")
    room_doc_path = story.get('room_doc_path', f"agent_framework/docs/US-{story['id']}.md")
    try:
        task['version'] = update_task_status(task['id'], qa_status, task.get('version'))
    except RuntimeError as exc:
        _append_room_log(room_doc_path, "QA", f"Task {task['id']} QA status sync failed", [f"- Error: {exc}"])
        return {"error": True, "error_message": str(exc), "next_step": "FINISH"}
    print(f"QA result for task {task['id']}: {qa_status}")
    qa_log_lines = [f"- Status: {qa_status}"]
    if result.get("feedback"):
        qa_log_lines.append(f"- Feedback: {result['feedback']}")
    artifacts = result.get("artifacts") or []
    if artifacts:
        qa_log_lines.append("- Artifacts:")
        qa_log_lines.extend([f"  - {artifact}" for artifact in artifacts])
    _append_room_log(room_doc_path, "QA", f"Task {task['id']} QA run", qa_log_lines)

    if qa_status == "QA Failed":
        retries = state.get('retries', {})
        current_retries = retries.get(task['id'], 0) + 1
        retries[task['id']] = current_retries
        print(f"Task {task['id']} failed QA. Retry attempt {current_retries}/{MAX_RETRIES}.")
        return {"next_step": "DEV", "feedback_for_dev": result.get("feedback"), "retries": retries}
    else:
        return {"current_task_index": task_index + 1, "next_step": "DEV", "retries": {}}

# --- 5. Router (Sửa lỗi xử lý max_retries) ---
def router(state: GraphState) -> str:
    if state.get("error"):
        print(f"[Router] Error detected: {state.get('error_message')}. Ending workflow.")
        return END

    next_step = state.get("next_step", "PLAN")
    print(f"[Router] Deciding next step from: {next_step}")

    if next_step == "PLAN":
        return "plan_node"
    
    if next_step == "QA":
        return "qa_node"

    if next_step == "DEV":
        task_index = state.get("current_task_index", 0)
        if task_index >= len(state.get("tasks", [])):
            print("[Router] All tasks completed. Ending workflow.")
            return END
            
        task = state["tasks"][task_index]
        retries = state.get('retries', {}).get(task['id'], 0)
        if retries >= MAX_RETRIES:
            print(f"[Router] Task {task['id']} exceeded max retries ({MAX_RETRIES}). Failing task and continuing.")
            try:
                task['version'] = update_task_status(task['id'], "Failed", task.get('version'))
            except RuntimeError as exc:
                print(f"[Router] Failed to mark task {task['id']} as Failed due to version mismatch: {exc}")
            # Loại bỏ retry entry cho task đã fail
            retries_map = state.get("retries", {})
            if task['id'] in retries_map:
                retries_map.pop(task['id'], None)
            # Tăng index để chuyển sang task tiếp theo
            state["current_task_index"] = task_index + 1
            story = get_story_by_id(state['story_id'])
            room_doc_path = story.get('room_doc_path') if story else None
            _append_room_log(
                room_doc_path or "",
                task['assignee_role'],
                f"Task {task['id']} exceeded retries",
                [f"- Marked as Failed after {MAX_RETRIES} QA attempts."]
            )
            # Refresh task snapshot to keep versions in sync for following nodes
            state["tasks"] = get_tasks_for_story(state['story_id'])
            # Kiểm tra lại xem đã hết task chưa
            if state["current_task_index"] >= len(state.get("tasks", [])):
                print("[Router] All tasks completed. Ending workflow.")
                return END
            return "dev_node"
            
        return "dev_node"
    
    return END

# --- 6. Xây dựng Graph ---

workflow = StateGraph(GraphState)

workflow.add_node("plan_node", plan_node)
workflow.add_node("dev_node", dev_node)
workflow.add_node("qa_node", qa_node)

workflow.set_entry_point("plan_node")

workflow.add_conditional_edges("plan_node", router, {"dev_node": "dev_node", END: END})
workflow.add_conditional_edges("dev_node", router, {"qa_node": "qa_node", END: END})
workflow.add_conditional_edges("qa_node", router, {"dev_node": "dev_node", END: END})

app = workflow.compile()

async def run_story_workflow(story_id: str, story_objective: str):
    """Configures and runs the agent workflow for a given story."""
    initial_state = {
        "story_id": story_id, 
        "story_objective": story_objective, 
        "current_task_index": 0,
        "tasks": [],
        "retries": {},
        "next_step": "PLAN",
        "error": False,
        "feedback_for_dev": None,
        "error_message": None
    }
    print(f"--- Starting Workflow for Story: {story_id} ---")
    async for event in app.astream(initial_state):
        for key, value in event.items():
            print(f"\nNode: {key} | Output: {value}\n")
    print(f"--- Workflow Finished for Story: {story_id} ---")

if __name__ == "__main__":
    from agent_framework.db.seed import main as seed_main
    seed_main()
    # Example of running a workflow directly
    asyncio.run(run_story_workflow("G1", "Deliver the frontend dashboard for project status."))
