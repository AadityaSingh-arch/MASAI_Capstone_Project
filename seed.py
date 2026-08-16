"""
Section 2, Task 5 — seeding helper.

Generates synthetic in-memory task dictionaries shaped exactly like the
fields the /tasks endpoints operate on (title, priority, due_date), at three
sizes (10 / 500 / 3000). Used by benchmark.py so the counted comparisons
reflect the same engine that powers the sort/search endpoints.

Run directly to also insert a small real sample into the actual database
(via the same SQLAlchemy models/session used by the app) so the stats and
search endpoints have real rows to exercise during manual testing.
"""
import random
import string
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PRIORITIES = ["low", "medium", "high"]
DUE_DATE_HINTS = [None, "today", "tomorrow", "next friday", "monday", "2026-09-01"]


def _random_title(n: int) -> str:
    words = ["Fix", "Restock", "Audit", "Update", "Review", "Deploy", "Inspect", "Clean", "Sync", "Patch"]
    subjects = ["conveyor", "shelves", "freezer", "packer", "router", "invoice", "sensor", "dashboard", "batch", "queue"]
    return f"{random.choice(words)} {random.choice(subjects)} #{n}"


def generate_synthetic_tasks(n: int) -> list:
    """Generate n synthetic task dicts with the same fields the sort/search
    endpoints operate on: id, title, priority, due_date."""
    tasks = []
    for i in range(n):
        tasks.append(
            {
                "id": i + 1,
                "title": _random_title(i),
                "priority": random.choice(PRIORITIES),
                "due_date": random.choice(DUE_DATE_HINTS),
            }
        )
    return tasks


def seed_real_database(num_tasks: int = 30):
    """Insert a small real sample into the actual SQLite DB via the app's
    own models/session, for manual end-to-end testing of the dashboard and
    endpoints (not used by the benchmark itself, which uses synthetic data
    at larger sizes for speed/reproducibility)."""
    from backend.database import SessionLocal, engine, Base
    from backend import models

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == "ops@blinkit.example").first()
        if not user:
            user = models.User(email="ops@blinkit.example", name="Ops Pod Lead")
            db.add(user)
            db.commit()
            db.refresh(user)

        project = db.query(models.Project).filter(models.Project.name == "Dark Store Rollout").first()
        if not project:
            project = models.Project(name="Dark Store Rollout", description="Seed project", owner_id=user.id)
            db.add(project)
            db.commit()
            db.refresh(project)

        existing_count = db.query(models.Task).filter(models.Task.project_id == project.id).count()
        to_create = max(0, num_tasks - existing_count)
        for i in range(to_create):
            t = models.Task(
                title=_random_title(existing_count + i),
                priority=random.choice(PRIORITIES),
                due_date=random.choice(DUE_DATE_HINTS),
                status="todo",
                project_id=project.id,
            )
            db.add(t)
        db.commit()
        print(f"Seeded project '{project.name}' (id={project.id}) with {to_create} new tasks "
              f"({db.query(models.Task).filter(models.Task.project_id == project.id).count()} total).")
    finally:
        db.close()


if __name__ == "__main__":
    seed_real_database(30)
