"""
TaskFlow backend — single FastAPI service covering all three graded
sections:
  Section 1: CRUD for users/projects/tasks + stats endpoint
  Section 2: GET /tasks?sort=... and GET /tasks/search?... (algorithms.py)
  Section 3: POST /tasks/quick-add (ai_parser.py)

Run with:
    uvicorn backend.main:app --reload
from the repository root (see README for full instructions).
"""
import logging
import os
import time
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, schemas
from .database import engine, get_db, init_db
from .algorithms import insertion_sort, binary_search, linear_search, priority_to_rank
from .ai_parser import mock_parse_task, build_prompt_messages

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("taskflow")

app = FastAPI(title="TaskFlow API")

# ---------------------------------------------------------------------------
# Bootstrap defaults — fixed identifiers so re-running is idempotent even
# under concurrent startups (handled via IntegrityError + rollback below).
# ---------------------------------------------------------------------------
BOOTSTRAP_USER_EMAIL = "ops@taskflow.local"
BOOTSTRAP_USER_NAME = "Ops Pod"
BOOTSTRAP_PROJECT_NAME = "Dark Store Ops"


def _get_or_create_bootstrap_user(db: Session) -> models.User:
    user = db.query(models.User).filter(models.User.email == BOOTSTRAP_USER_EMAIL).first()
    if user:
        logger.info(f"Bootstrap user already exists (id={user.id}) — skipping creation.")
        return user
    user = models.User(email=BOOTSTRAP_USER_EMAIL, name=BOOTSTRAP_USER_NAME)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Another process/startup created it concurrently — fall back to reading it.
        db.rollback()
        user = db.query(models.User).filter(models.User.email == BOOTSTRAP_USER_EMAIL).first()
        logger.info("Bootstrap user creation raced with another writer; reused existing row.")
        return user
    db.refresh(user)
    logger.info(f"Created bootstrap user (id={user.id}, email={user.email}).")
    return user


def _get_or_create_bootstrap_project(db: Session, owner: models.User) -> models.Project:
    project = (
        db.query(models.Project)
        .filter(models.Project.name == BOOTSTRAP_PROJECT_NAME, models.Project.owner_id == owner.id)
        .first()
    )
    if project:
        logger.info(f"Bootstrap project already exists (id={project.id}) — skipping creation.")
        return project
    project = models.Project(
        name=BOOTSTRAP_PROJECT_NAME,
        description="Default project created automatically on first run",
        owner_id=owner.id,
    )
    db.add(project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        project = (
            db.query(models.Project)
            .filter(models.Project.name == BOOTSTRAP_PROJECT_NAME, models.Project.owner_id == owner.id)
            .first()
        )
        logger.info("Bootstrap project creation raced with another writer; reused existing row.")
        return project
    db.refresh(project)
    logger.info(f"Created bootstrap project (id={project.id}, owner_id={project.owner_id}).")
    return project


@app.on_event("startup")
def on_startup():
    """Runs once per process start. Order matters: tables must exist before
    we can query/insert the bootstrap user, and the bootstrap user must
    exist before we can insert the bootstrap project (owner_id FK)."""
    logger.info("=== TaskFlow startup: initializing database ===")
    init_db()

    db = next(get_db())
    try:
        user = _get_or_create_bootstrap_user(db)
        if user is None:
            logger.error("Bootstrap user could not be created or found — a valid user is "
                         "required before any project/task can exist.")
            return
        project = _get_or_create_bootstrap_project(db, user)
        if project is None:
            logger.error("Bootstrap project could not be created or found — task creation "
                         "will fail without a valid project_id.")
            return
        logger.info(
            f"Startup bootstrap complete: user_id={user.id}, project_id={project.id}. "
            f"A valid project now exists before any task creation is attempted."
        )
    finally:
        db.close()
    logger.info("=== TaskFlow startup complete ===")


# ---------------------------------------------------------------------------
# CORS (Section 1, Task 8) — explicit origin, explicit methods/headers.
# Override via env var if the frontend is served from a different origin.
# The frontend's API_BASE (script.js) must point at this same host:port.
# ---------------------------------------------------------------------------
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://127.0.0.1:5500")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ---------------------------------------------------------------------------
# Custom middleware (Section 1, Task 7) — logs method, path, status, and
# duration (ms) for every request. Failed requests (>=400) get an extra,
# more detailed log line to make debugging easier without needing to
# reproduce the request.
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            f"UNHANDLED ERROR: {request.method} {request.url.path} "
            f"(client={request.client.host if request.client else 'unknown'}) "
            f"after {duration_ms:.2f}ms"
        )
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.2f}ms)")
    if response.status_code >= 400:
        logger.warning(
            f"FAILED REQUEST: {request.method} {request.url.path} "
            f"query={dict(request.query_params)} -> {response.status_code} "
            f"(client={request.client.host if request.client else 'unknown'}, {duration_ms:.2f}ms)"
        )
    return response


# ---------------------------------------------------------------------------
# Exception handlers — every error response is JSON with a clear, specific
# message rather than a generic failure or an HTML error page.
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """422 with a flattened, human-readable list of what failed and where,
    instead of FastAPI's raw nested error structure."""
    field_errors = []
    for err in exc.errors():
        loc = " -> ".join(str(p) for p in err.get("loc", []) if p != "body")
        field_errors.append({"field": loc, "message": err.get("msg", "Invalid value")})
    logger.warning(f"Validation error on {request.method} {request.url.path}: {field_errors}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation failed", "errors": field_errors},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """A DB constraint violation (e.g. duplicate email) surfaces as a clear
    422 instead of an opaque 500."""
    logger.warning(f"Integrity error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": "The request conflicts with existing data (e.g. a duplicate value)."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last-resort handler: guarantees every response is JSON, even for
    exceptions we didn't anticipate, and logs the full traceback for
    debugging."""
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. Check the server logs."},
    )


# ===========================================================================
# Section 1 — Users
# ===========================================================================
@app.post("/users", response_model=schemas.UserResponse, status_code=201)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=422, detail="A user with this email already exists")
    db_user = models.User(email=user.email, name=user.name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/users", response_model=List[schemas.UserResponse])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()


# ===========================================================================
# Section 1 — Projects
# ===========================================================================
@app.post("/projects", response_model=schemas.ProjectResponse, status_code=201)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db)):
    owner = db.query(models.User).filter(models.User.id == project.owner_id).first()
    if not owner:
        raise HTTPException(status_code=422, detail=f"No user with id {project.owner_id}")
    db_project = models.Project(
        name=project.name, description=project.description, owner_id=project.owner_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@app.get("/projects", response_model=List[schemas.ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(models.Project).all()


@app.get("/projects/{project_id}", response_model=schemas.ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ---------------------------------------------------------------------------
# Section 1, Task 6 — per-project statistics, aggregated in SQL (not Python)
# ---------------------------------------------------------------------------
@app.get("/projects/{project_id}/stats", response_model=schemas.ProjectStats)
def project_stats(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    total = (
        db.query(func.count(models.Task.id))
        .join(models.Project, models.Task.project_id == models.Project.id)
        .filter(models.Project.id == project_id)
        .scalar()
    )

    rows = (
        db.query(models.Task.status, func.count(models.Task.id))
        .join(models.Project, models.Task.project_id == models.Project.id)
        .filter(models.Project.id == project_id)
        .group_by(models.Task.status)
        .all()
    )
    status_counts = {status: count for status, count in rows}

    return schemas.ProjectStats(
        project_id=project.id,
        project_name=project.name,
        task_count=total or 0,
        status_counts=status_counts,
    )


# ===========================================================================
# Section 1 — Tasks (full CRUD)
# ===========================================================================
@app.post("/tasks", response_model=schemas.TaskResponse, status_code=201)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=422, detail=f"No project with id {task.project_id}")
    db_task = models.Task(
        title=task.title,
        description=task.description,
        priority=task.priority,
        due_date=task.due_date,
        status=task.status,
        project_id=task.project_id,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@app.get("/tasks", response_model=List[schemas.TaskResponse])
def list_tasks(
    sort: Optional[str] = None,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Plain listing, or — when ?sort=priority|due_date is given — the same
    endpoint delegates ordering to Section 2's insertion_sort (never a
    built-in sort). See /tasks/search for the search counterpart."""
    query = db.query(models.Task)
    if project_id is not None:
        query = query.filter(models.Task.project_id == project_id)
    db_tasks = query.all()

    records = [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "priority": t.priority,
            "due_date": t.due_date,
            "status": t.status,
            "project_id": t.project_id,
            "_priority_rank": priority_to_rank(t.priority),
        }
        for t in db_tasks
    ]

    if sort == "priority":
        insertion_sort(records, "_priority_rank")
    elif sort == "due_date":
        # Nulls sort last: give them a sentinel that is always "greater".
        for r in records:
            r["_due_date_sort_key"] = r["due_date"] or "\uffff"
        insertion_sort(records, "_due_date_sort_key")

    return records


@app.get("/tasks/search", response_model=schemas.TaskResponse)
def search_tasks(
    title: str,
    algo: str = "binary",
    db: Session = Depends(get_db),
):
    """Exact-title lookup over the real tasks table using Section 2's
    hand-rolled binary_search (default) or linear_search. Deliberately
    global (not project-scoped) — titles are matched exactly across the
    whole tasks table, matching the graded spec for this endpoint."""
    db_tasks = db.query(models.Task).all()
    index_records = [{"id": t.id, "title": t.title} for t in db_tasks]

    if algo == "linear":
        match_idx = linear_search(index_records, title, "title")
    else:
        insertion_sort(index_records, "title")
        match_idx = binary_search(index_records, title, "title")

    if match_idx is None:
        raise HTTPException(status_code=404, detail=f"No task with title '{title}'")

    matched_id = index_records[match_idx]["id"]
    task = db.query(models.Task).filter(models.Task.id == matched_id).first()
    return task


@app.get("/tasks/{task_id}", response_model=schemas.TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/tasks/{task_id}", response_model=schemas.TaskResponse)
def update_task(task_id: int, task_update: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = task_update.model_dump(exclude_unset=True)

    if "project_id" in update_data and update_data["project_id"] is not None:
        project = db.query(models.Project).filter(models.Project.id == update_data["project_id"]).first()
        if not project:
            raise HTTPException(status_code=422, detail=f"No project with id {update_data['project_id']}")

    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@app.delete("/tasks/{task_id}", status_code=200)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"detail": "Task deleted", "id": task_id}


# ===========================================================================
# Section 3 — AI Quick-Add
# ===========================================================================
@app.post("/tasks/quick-add", response_model=schemas.TaskResponse, status_code=201)
def quick_add_task(payload: schemas.QuickAddRequest, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=422, detail=f"No project with id {payload.project_id}")

    # Role-based prompt structure, built regardless of which backend answers it.
    _messages = build_prompt_messages(payload.description)

    use_real_llm = os.environ.get("USE_REAL_LLM", "").lower() in ("1", "true", "yes")
    parsed = None
    if use_real_llm:
        try:
            from . import real_llm_parser  # optional, feature-flagged, off by default

            parsed = real_llm_parser.parse_task(_messages)
        except Exception:
            logger.warning("USE_REAL_LLM is set but the real LLM call failed; falling back to mock parser.")
            parsed = None  # fall back to the mock on any error / missing key

    if parsed is None:
        parsed = mock_parse_task(payload.description)

    # Validate the (mock or real) parse against the Pydantic Task model
    # before writing anything to the database.
    try:
        candidate = schemas.TaskCreate(
            title=parsed["title"],
            priority=parsed["priority"],
            due_date=parsed.get("due_date_hint"),
            project_id=payload.project_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    db_task = models.Task(
        title=candidate.title,
        description=None,
        priority=candidate.priority,
        due_date=candidate.due_date,
        status="todo",
        project_id=candidate.project_id,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


# ===========================================================================
# Optional single-process static-file serving of the frontend.
# Only kicks in if frontend/ exists relative to the repo root, so the
# two-process dev workflow (README default) is unaffected either way.
# ===========================================================================
_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
