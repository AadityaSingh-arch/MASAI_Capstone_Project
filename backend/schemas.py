"""
Pydantic request/response models.

Task models include:
- a Field constraint restricting priority to the closed set
  low/medium/high (Section 1, Task 3)
- a custom validator rejecting a blank title after trimming whitespace
"""
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str


# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    owner_id: int


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    owner_id: int


# ---------------------------------------------------------------------------
# Task schemas
# ---------------------------------------------------------------------------
PriorityLiteral = Literal["low", "medium", "high"]


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    priority: PriorityLiteral = "medium"
    due_date: Optional[str] = None
    status: str = Field(default="todo")
    project_id: int

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("title must not be blank")
        return trimmed


class TaskUpdate(BaseModel):
    """All fields optional so PATCH-style partial updates work via PUT."""

    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[PriorityLiteral] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    project_id: Optional[int] = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("title must not be blank")
        return trimmed


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    priority: PriorityLiteral
    due_date: Optional[str] = None
    status: str
    project_id: int


# ---------------------------------------------------------------------------
# Statistics schema
# ---------------------------------------------------------------------------
class ProjectStats(BaseModel):
    project_id: int
    project_name: str
    task_count: int
    status_counts: dict


# ---------------------------------------------------------------------------
# AI Quick-Add schema (Section 3)
# ---------------------------------------------------------------------------
class QuickAddRequest(BaseModel):
    description: str = Field(..., min_length=1)
    project_id: int
