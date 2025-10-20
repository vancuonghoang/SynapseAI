from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Literal

import yaml
from langgraph.graph import StateGraph, END

from orchestrator.ctb import CTB
from orchestrator.llm_client import LLMClient, LLMConfig
from orchestrator.db import (
    get_tasks_for_story,
    update_task_status,
    get_story_by_id,
    update_story_room_doc,
)
from orchestrator.agents.pm import PMAgent
from orchestrator.agents.devops import DevOpsAgent
from orchestrator.agents.be import BEAgent
from orchestrator.agents.ml import MLAgent
from orchestrator.agents.qa import QAAgent
from orchestrator.agents.fe import FEAgent


BASE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BASE_DIR.parent


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


def load_role_guards() -> Dict[str, List[str]]:
    config_dir = BASE_DIR / "config"
    roles_path = config_dir / "roles.yaml"
    try:
        with open(roles_path, "r", encoding="utf-8") as f:
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
        provider=cfg.get("provider", default_provider),
    )


def build_llm_client() -> LLMClient:
    config_path = BASE_DIR / "config" / "models.yaml"
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
        except Exception as exc:  # pragma: no cover - log and fallback
            print(f"[LLM Config] Failed to load models.yaml: {exc}. Falling back to defaults.")
            role_to_config = {}
            overrides = {"tasks": {}, "stories": {}}
    else:
        print("[LLM Config] models.yaml not found; using in-code defaults.")

    if not role_to_config:
        role_to_config = {
            "PM": LLMConfig(name="gpt-4o", temperature=0.2, provider=default_provider),
            "DevOps": LLMConfig(name="gpt-4o-mini", temperature=0.2, provider=default_provider),
            "BE": LLMConfig(name="gpt-4o", temperature=0.2, provider=default_provider),
            "ML": LLMConfig(name="gpt-4o", temperature=0.1, provider=default_provider),
            "QA": LLMConfig(name="gpt-4o-mini", temperature=0.1, provider=default_provider),
            "FE": LLMConfig(name="gpt-4o-mini", temperature=0.3, provider=default_provider),
        }

    return LLMClient(default_provider=default_provider, role_to_config=role_to_config, overrides=overrides)


def agent_factory(role: str, llm: LLMClient):
    factory = {
        "PM": PMAgent,
        "DevOps": DevOpsAgent,
        "BE": BEAgent,
        "ML": MLAgent,
        "QA": QAAgent,
        "FE": FEAgent,
    }
    if role not in factory:
        raise ValueError(f"Unknown agent role: {role}")
    return factory[role](llm)


def _build_ctb(task: Dict[str, Any], story: Dict[str, Any], role_override: Optional[str] = None) -> CTB:
    role = role_override or task["assignee_role"]
    task_id = f"{task['id']}.{role_override}" if role_override else task["id"]
    room_doc_path = story.get("room_doc_path", f"agent_framework/docs/US-{story['id']}.md")
    try:
        attachments = {
            "AGENTS.MD": (ROOT_DIR / "agent_framework" / "AGENTS.MD").read_text(encoding="utf-8"),
            "BACKLOG.md": (ROOT_DIR / "agent_framework" / "BACKLOG.md").read_text(encoding="utf-8"),
            "ROOM.md": Path(room_doc_path).read_text(encoding="utf-8") if os.path.exists(room_doc_path) else "",
        }
    except FileNotFoundError as exc:
        print(f"[Error] Failed to read attachment file: {exc}")
        raise
    return CTB(
        task_id=task_id,
        role=role,
        story_id=story["id"],
        objective=task["description"],
        constraints=["Follow AGENTS.MD rules"],
        attachments=attachments,
        guard_paths=ROLE_GUARDS.get(role, []),
        acceptance=task.get("acceptance", []),
        llm={},
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


async def plan_node(state: GraphState) -> Dict[str, Any]:
    print("\n--- Executing Planning Node ---")
    story_id = state["story_id"]
    room_doc_path = f"agent_framework/docs/US-{story_id}.md"
    Path("agent_framework/docs").mkdir(exist_ok=True)
    if not os.path.exists(room_doc_path):
        Path(room_doc_path).write_text(
            f"# User Story: {story_id}\n\nObjective: {state['story_objective']}\n\n",
            encoding="utf-8",
        )
        update_story_room_doc(story_id, room_doc_path)
        print(f"Created Room Doc: {room_doc_path}")

    llm = build_llm_client()
    pm_agent = agent_factory("PM", llm)
    try:
        attachments = {
            "AGENTS.MD": (ROOT_DIR / "agent_framework" / "AGENTS.MD").read_text(encoding="utf-8"),
            "BACKLOG.md": (ROOT_DIR / "agent_framework" / "BACKLOG.md").read_text(encoding="utf-8"),
            "ROOM.md": Path(room_doc_path).read_text(encoding="utf-8"),
        }
    except FileNotFoundError as exc:
        return {"error": True, "error_message": f"Failed to build CTB for PM: {exc}"}

    pm_ctb = CTB(
        task_id=f"{story_id}.PLAN",
        role="PM",
        story_id=story_id,
        objective=state["story_objective"],
        constraints=[
            "Break down into tasks for DevOps, BE, FE, ML, and QA roles",
            "Target freqtrade layout (user_data/strategies/, user_data/config.json, user_data/freqai/)"
        ],
        attachments=attachments,
        guard_paths=ROLE_GUARDS.get("PM", []),
        acceptance=["Tasks are created in DB"],
        llm={},
    )

    result = await pm_agent.run(pm_ctb)
    if result.get("status") == "Failed":
        return {"error": True, "error_message": result.get("error", "Planning failed")}

    tasks = get_tasks_for_story(story_id)
    if not tasks:
        return {"error": True, "error_message": f"No tasks found for story {story_id} after planning."}

    summary_lines = [
        f"- {task['id']} ({task['assignee_role']} – est {task.get('estimate', '?')}): {task['description']}"
        for task in tasks
    ]
    _append_room_log(room_doc_path, "PM", "Planning completed", summary_lines)

    return {"tasks": tasks, "current_task_index": 0, "next_step": "DEV", "retries": {}}


async def dev_node(state: GraphState) -> Dict[str, Any]:
    task_index = state["current_task_index"]
    task = state["tasks"][task_index]
    print(f"\n--- Executing DEV Node for Task: {task['id']} ({task['assignee_role']}) ---")

    story = get_story_by_id(state["story_id"])
    if not story:
        return {"error": True, "error_message": f"Story {state['story_id']} not found."}

    try:
        ctb = _build_ctb(task, story)
    except FileNotFoundError:
        return {"error": True, "error_message": "Failed to build CTB due to missing attachments."}

    if state.get("feedback_for_dev"):
        ctb.objective += f"\n\n**QA FEEDBACK:** {state['feedback_for_dev']}"

    llm = build_llm_client()
    worker_agent = agent_factory(task["assignee_role"], llm)

    room_doc_path = story.get("room_doc_path", f"agent_framework/docs/US-{story['id']}.md")
    update_task_status(task["id"], "In Progress")
    result = await worker_agent.run(ctb)
    final_status = result.get("status", "Coding Complete")
    update_task_status(task["id"], final_status)

    log_lines = [f"- Objective: {ctb.objective}", f"- Status: {final_status}"]
    artifacts = result.get("artifacts") or []
    if artifacts:
        log_lines.append("- Artifacts:")
        log_lines.extend([f"  - {artifact}" for artifact in artifacts])
    if result.get("error"):
        log_lines.append(f"- Error: {result['error']}")
    _append_room_log(room_doc_path, task["assignee_role"], f"Task {task['id']} execution", log_lines)

    if final_status == "Failed":
        return {"error": True, "error_message": result.get("error", "Dev agent failed to execute."), "next_step": "FINISH"}

    return {"next_step": "QA", "feedback_for_dev": None}


async def qa_node(state: GraphState) -> Dict[str, Any]:
    task_index = state["current_task_index"]
    task = state["tasks"][task_index]
    print(f"\n--- Executing QA Node for Task: {task['id']} ---")

    story = get_story_by_id(state["story_id"])
    if not story:
        return {"error": True, "error_message": f"Story {state['story_id']} not found."}

    try:
        ctb = _build_ctb(task, story, role_override="QA")
    except FileNotFoundError:
        return {"error": True, "error_message": "Failed to build CTB for QA due to missing attachments."}

    llm = build_llm_client()
    qa_agent = agent_factory("QA", llm)
    result = await qa_agent.run(ctb)

    qa_status = result.get("status", "Done")
    update_task_status(task["id"], qa_status)

    room_doc_path = story.get("room_doc_path", f"agent_framework/docs/US-{story['id']}.md")
    qa_log_lines = [f"- Status: {qa_status}"]
    if result.get("feedback"):
        qa_log_lines.append(f"- Feedback: {result['feedback']}")
    artifacts = result.get("artifacts") or []
    if artifacts:
        qa_log_lines.append("- Artifacts:")
        qa_log_lines.extend([f"  - {artifact}" for artifact in artifacts])
    _append_room_log(room_doc_path, "QA", f"Task {task['id']} QA run", qa_log_lines)

    if qa_status == "QA Failed":
        retries = state.get("retries", {})
        retries[task["id"]] = retries.get(task["id"], 0) + 1
        print(f"Task {task['id']} failed QA. Retry attempt {retries[task['id']]}/{MAX_RETRIES}.")
        return {"next_step": "DEV", "feedback_for_dev": result.get("feedback"), "retries": retries}

    return {"current_task_index": task_index + 1, "next_step": "DEV", "retries": {}}


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
        tasks = state.get("tasks", [])
        if task_index >= len(tasks):
            print("[Router] All tasks completed. Ending workflow.")
            return END

        task = tasks[task_index]
        retries = state.get("retries", {}).get(task["id"], 0)
        if retries >= MAX_RETRIES:
            print(f"[Router] Task {task['id']} exceeded max retries ({MAX_RETRIES}). Failing task and continuing.")
            update_task_status(task["id"], "Failed")
            story = get_story_by_id(state["story_id"])
            room_doc_path = story.get("room_doc_path") if story else None
            _append_room_log(
                room_doc_path or "",
                task["assignee_role"],
                f"Task {task['id']} exceeded retries",
                [f"- Marked as Failed after {MAX_RETRIES} QA attempts."],
            )
            retries_map = state.get("retries", {})
            retries_map.pop(task["id"], None)
            state["current_task_index"] = task_index + 1
            state["tasks"] = get_tasks_for_story(state["story_id"])
            if state["current_task_index"] >= len(state.get("tasks", [])):
                print("[Router] All tasks completed. Ending workflow.")
                return END
            return "dev_node"
        return "dev_node"

    return END


workflow = StateGraph(GraphState)
workflow.add_node("plan_node", plan_node)
workflow.add_node("dev_node", dev_node)
workflow.add_node("qa_node", qa_node)
workflow.set_entry_point("plan_node")
workflow.add_conditional_edges("plan_node", router, {"dev_node": "dev_node", END: END})
workflow.add_conditional_edges("dev_node", router, {"qa_node": "qa_node", END: END})
workflow.add_conditional_edges("qa_node", router, {"dev_node": "dev_node", END: END})
app = workflow.compile()


async def run_story_workflow(story_id: str, story_objective: str) -> None:
    initial_state: GraphState = {
        "story_id": story_id,
        "story_objective": story_objective,
        "current_task_index": 0,
        "tasks": [],
        "retries": {},
        "next_step": "PLAN",
        "error": False,
        "feedback_for_dev": None,
        "error_message": None,
    }
    print(f"--- Starting Workflow for Story: {story_id} ---")
    async for event in app.astream(initial_state):
        for key, value in event.items():
            print(f"\nNode: {key} | Output: {value}\n")
    print(f"--- Workflow Finished for Story: {story_id} ---")


if __name__ == "__main__":  # pragma: no cover
    from agent_framework.db.seed import main as seed_main

    seed_main()
    asyncio.run(run_story_workflow("G1", "Deliver the frontend dashboard for project status."))
