from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

# Tải các biến môi trường từ file .env
load_dotenv()

class LLMConfig(BaseModel):
    """Cấu hình cho một model LLM cụ thể."""
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 4000
    system_prompt: str

class LLMProvider(BaseModel):
    """Cấu hình cho một nhà cung cấp LLM (ví dụ: OpenAI)."""
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    models: Dict[str, LLMConfig]

class Config(BaseModel):
    """Cấu hình tổng cho toàn bộ hệ thống LLM."""
    providers: Dict[str, LLMProvider]

def load_config() -> Config:
    """Tải và định nghĩa các cấu hình LLM."""
    planner_system_prompt = ("""
    You are an expert project manager AI. Your role is to break down a user story into a series of specific, actionable tasks for a team of AI agents.
    Based on the user story, the project backlog, and the agent constitution (AGENTS.MD), generate a JSON list of tasks.
    Each task must have: id, description, assigned_to (one of ["Data", "ML/Quant", "Backend", "DevOps"]), and dependencies (a list of task ids).
    Respond ONLY with the valid JSON list.
    """)

    config_data = {
        "providers": {
            "openai": {
                "models": {
                    "planner": {
                        "model_name": "gpt-4-turbo-preview",
                        "temperature": 0.5,
                        "max_tokens": 4096,
                        "system_prompt": planner_system_prompt
                    },
                    "planner_pm": {
                        "model_name": "gpt-4o",
                        "temperature": 0.2,
                        "max_tokens": 2048,
                        "system_prompt": "You are an expert Project Manager AI. Your role is to break down a user story into a JSON list of specific, actionable tasks for a team of AI agents. Each task must have: id, description, assigned_to (one of [\"Data\", \"ML/Quant\", \"Backend\", \"DevOps\"]), and dependencies."
                    },
                    "coder": {
                        "model_name": "gpt-4-turbo-preview",
                        "temperature": 0.6,
                        "max_tokens": 4096,
                        "system_prompt": "You are an expert software engineer. Write clean, efficient, and correct code based on the provided context and task."
                    }
                }
            }
        }
    }
    return Config(**config_data)
