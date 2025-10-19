import asyncio
from dataclasses import dataclass, replace
from typing import Dict, Optional, Any

@dataclass
class LLMConfig:
    name: str
    temperature: float = 0.2
    max_tokens: int = 2000
    provider: Optional[str] = None

class LLMClient:
    """Mô phỏng LLM Client có khả năng chọn model theo vai trò và task."""
    def __init__(self, default_provider: str, role_to_config: Dict[str, LLMConfig], overrides: Dict[str, Dict[str, LLMConfig]]):
        self.default_provider = default_provider
        self.role_to_config = role_to_config
        self.overrides = overrides or {"tasks": {}, "stories": {}}
        for key in ("tasks", "stories"):
            self.overrides.setdefault(key, {})
        print(f"[LLMClient] Initialized with default provider: {self.default_provider}")

    def _with_defaults(self, config: LLMConfig, fallback_role: Optional[str] = None) -> LLMConfig:
        provider = config.provider or (self.role_to_config.get(fallback_role).provider if fallback_role and fallback_role in self.role_to_config else None) or self.default_provider
        return replace(config, provider=provider)

    def pick_config(self, role: str, task_id: Optional[str] = None, story_id: Optional[str] = None) -> LLMConfig:
        if task_id and task_id in self.overrides.get("tasks", {}):
            print(f"[LLMClient] Override found for task {task_id}.")
            return self._with_defaults(self.overrides["tasks"][task_id], role)
        if story_id and story_id in self.overrides.get("stories", {}):
            print(f"[LLMClient] Override found for story {story_id}.")
            return self._with_defaults(self.overrides["stories"][story_id], role)
        if role in self.role_to_config:
            return self._with_defaults(self.role_to_config[role], role)
        print(f"[LLMClient] No config found for role {role}; falling back to defaults.")
        return LLMConfig(name="gpt-4o", temperature=0.2, max_tokens=2000, provider=self.default_provider)

    async def complete(self, role: str, system_prompt: str, user_prompt: str, task_id: Optional[str] = None, story_id: Optional[str] = None) -> str:
        config = self.pick_config(role, task_id, story_id)
        print(f"[LLMClient] Calling provider {config.provider} model {config.name} for role {role} (temp={config.temperature})...")
        await asyncio.sleep(1) # Simulate network latency
        # PSEUDOCODE: In a real system, you would call the LLM API here.
        # e.g., return openai.chat.completions.create(...)
        
        # Mock response for development
        if role == "PM":
            return """[
    {
        "id": "A1.T01", "kind": "impl", "description": "Create docker-compose.yml for all services",
        "assignee_role": "DevOps", "dependencies": [], "acceptance": ["docker-compose up starts without errors"], "estimate": "S"
    },
    {
        "id": "A1.T02", "kind": "impl", "description": "Create a /health endpoint in the API",
        "assignee_role": "BE", "dependencies": ["A1.T01"], "acceptance": ["GET /health returns 200 OK"], "estimate": "M"
    },
    {
        "id": "A1.T03", "kind": "impl", "description": "Create a basic UI dashboard component",
        "assignee_role": "FE", "dependencies": ["A1.T02"], "acceptance": ["Component renders basic story list"], "estimate": "M"
    },
    {
        "id": "A1.T04", "kind": "test", "description": "Write and run integration tests for the /health endpoint",
        "assignee_role": "QA", "dependencies": ["A1.T03"], "acceptance": ["Tests pass successfully"], "estimate": "S"
    }
]"""
        elif role == "DevOps":
            return """version: '3.8'

services:
  api:
    build: ./workspace
    ports:
      - "8000:8000"
    env_file:
      - .env.api
    depends_on:
      - db

  db:
    image: postgres:13-alpine
    restart: unless-stopped
    env_file:
      - .env.db
    volumes:
      - postgres-data:/var/lib/postgresql/data

volumes:
  postgres-data:
"""
        elif role == "BE":
            return """from fastapi import APIRouter

router = APIRouter()

@router.get("/stories/{story_id}")
def get_story(story_id: str):
    # Logic to fetch story from DB will be implemented here
    return {"story_id": story_id, "title": "Sample Story"}
"""
        elif role == "QA":
            return """import pytest

def test_health_check():
    # This is a mock test. In a real scenario, it would test a real endpoint.
    response_status = 200
    assert response_status == 200, "Health check should return 200 OK"

def test_placeholder():
    assert True
"""
        elif role == "FE":
            return """import React from 'react';

interface DashboardProps {
  stories: any[];
}

const Dashboard: React.FC<DashboardProps> = ({ stories }) => {
  return (
    <div>
      <h1>Project Dashboard</h1>
      {stories.map(story => (
        <div key={story.id}>_story.title_</div>
      ))}
    </div>
  );
};

export default Dashboard;
"""

        return f"[MOCK COMPLETION for {role}] {user_prompt[:150]}..."
