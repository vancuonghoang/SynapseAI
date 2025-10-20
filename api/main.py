import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from typing import List, Dict, Any

from orchestrator.db import get_all_stories, get_story_by_id, get_tasks_for_story, get_artifacts_for_story
from orchestrator.graph import run_story_workflow

app = FastAPI(
    title="Multi-Agent System Orchestrator API",
    description="API to manage and run agent-based software development workflows.",
    version="1.0.0",
)

@app.get("/stories", response_model=List[Dict[str, Any]])
async def list_stories():
    """Lists all user stories and their associated tasks."""
    stories = get_all_stories()
    if not stories:
        return []
    
    response = []
    for story in stories:
        story_dict = dict(story)
        story_dict['tasks'] = get_tasks_for_story(story['id'])
        response.append(story_dict)
    return response

@app.post("/run/{story_id}", status_code=202)
async def run_story(story_id: str):
    """Triggers a new workflow run for a specific user story in the background."""
    story = get_story_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    # Use asyncio.create_task for fire-and-forget async background tasks
    asyncio.create_task(run_story_workflow(story_id, story['title']))
    
    return {"message": "Workflow triggered to run in the background.", "story_id": story_id}

@app.get("/status/{story_id}", response_model=Dict[str, Any])
async def get_story_status(story_id: str):
    """Gets the current status of a story and all its tasks."""
    story = get_story_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    tasks = get_tasks_for_story(story_id)
    story_dict = dict(story)
    story_dict['tasks'] = tasks
    return story_dict

@app.get("/artifacts/{story_id}", response_model=List[Dict[str, Any]])
async def list_artifacts(story_id: str):
    """Lists all artifacts associated with a specific user story."""
    story = get_story_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
        
    artifacts = get_artifacts_for_story(story_id)
    return artifacts

@app.get("/")
async def root():
    return {"message": "Agent Orchestrator API is running."}
