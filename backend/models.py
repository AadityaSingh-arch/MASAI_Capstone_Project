"""
SQLAlchemy ORM models: User -> Project -> Task.

Relational schema (Section 1, Task 1 & 2):
- users(id PK, email UNIQUE NOT NULL, name NOT NULL)
- projects(id PK, name NOT NULL, owner_id FK -> users.id NOT NULL)
- tasks(id PK, title NOT NULL, description, priority (low/medium/high),
        due_date TEXT (nullable, free text), status, project_id FK -> projects.id NOT NULL)
"""
from sqlalchemy import Column, Integer, String, ForeignKey, text, CheckConstraint
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)

    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    # Closed set: "low" / "medium" / "high" — enforced at the Pydantic layer
    # (schemas.py) and mirrored here with a server-side CHECK constraint.
    priority = Column(
        String,
        nullable=False,
        server_default=text("'medium'"),
    )
    # Intentionally plain text, not Date: a manually-typed date and an
    # AI-parsed phrase like "next friday" (Section 3) are both valid values.
    due_date = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default=text("'todo'"))
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    project = relationship("Project", back_populates="tasks")

    __table_args__ = (
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_task_priority"),
    )
