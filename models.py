from typing import Dict, Any, List, Literal, Optional
from pydantic import BaseModel, Field
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    FAILED = "FAILED"
    QA_PENDING = "QA_PENDING"
    QA_FAILED = "QA_FAILED"

class Task(BaseModel):
    id: str
    description: str
    assigned_to: Literal["Data", "ML/Quant", "Backend", "DevOps"]
    dependencies: List[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    artifacts: List[str] = Field(default_factory=list)
    feedback: Optional[str] = None

class ProjectPlan(BaseModel):
    phases: Dict[str, List[Task]]

class TaskResult(BaseModel):
    task_id: str
    status: Literal["SUCCESS", "FAILURE"]
    artifacts: List[str] = Field(default_factory=list)
    message: str

class QAResult(BaseModel):
    status: Literal["PASSED", "FAILED"]
    feedback: Optional[str] = None
