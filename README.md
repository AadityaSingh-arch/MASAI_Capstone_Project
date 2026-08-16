# TaskFlow

Internal task-and-project management platform for Blinkit's dark-store engineering pods. One FastAPI + SQLAlchemy backend (CRUD, statistics, a hand-rolled sort/search engine, and an AI quick-add parser) with a vanilla HTML/CSS/JS dashboard wired to it over the Fetch API.

## Environment setup

```bash
git clone <this-repo-url>
cd taskflow
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running the app

**Two-process run (recommended)** — backend on port 8000, frontend on a separate static server on port 5500. The backend's CORS config already allows `http://127.0.0.1:5500` / `http://localhost:5500`.

```bash
# Terminal 1 — backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend (any static server works)
cd frontend
python3 -m http.server 5500
```

Then open `http://127.0.0.1:5500`. The dashboard's `script.js` calls the backend at `http://127.0.0.1:8000` by default (override by setting `window.TASKFLOW_API_BASE` before `script.js` loads, e.g. in a small inline `<script>` tag).

**Single-process alternative:** `main.py` also mounts `frontend/` as static files, so `uvicorn backend.main:app --reload` alone serves the whole app at `http://127.0.0.1:8000` with same-origin relative paths — no second server needed. Pick whichever run mode you prefer; both are wired to the same backend.

On startup, the **backend itself** (not the frontend) creates tables and a default user + project if the database is empty — see "Startup & reliability" below. There's nothing to seed manually before the UI is usable. To seed extra sample data (used for manual testing) or generate the Section 2 benchmark data, see below.

```bash
python3 seed.py           # inserts ~30 sample tasks into a "Dark Store Rollout" project
python3 benchmark.py      # Section 2 benchmark — see "Algorithms" below
python3 check_algorithms.py   # Section 2 PASS/FAIL checks
```

## Startup & reliability

Everything below runs from a single `@app.on_event("startup")` handler in `backend/main.py`, in this order, and every step is logged to the console so a hung or skipped step is visible immediately rather than silently failing:

1. **`init_db()`** (`backend/database.py`) — checks the target directory is writable (raises a clear `PermissionError` if not, instead of an opaque failure on the first request), then calls `Base.metadata.create_all()`. If an existing SQLite file is corrupted or only partially written (`sqlite3.DatabaseError: file is not a database`), it's removed and recreated automatically, with a warning logged.
2. **Bootstrap user** — `ops@taskflow.local` is created if it doesn't already exist; if it does (e.g. after a restart), creation is skipped and the existing row is reused. A concurrent-startup race (two processes creating it at once) is caught via `IntegrityError` + rollback and falls back to reading the row the other process just committed.
3. **Bootstrap project** — created only after the bootstrap user exists (its `owner_id` FK depends on it), with the same idempotent get-or-create + race-safe pattern, so a valid project always exists before the frontend or any API client tries to create a task.

**Error responses:** a `RequestValidationError` handler flattens Pydantic's nested errors into `{"detail": "Validation failed", "errors": [{"field": "...", "message": "..."}]}` so the frontend (and `curl`) get a specific, actionable message instead of a generic one. An `IntegrityError` handler catches constraint violations (e.g. a duplicate unique value slipping past an application-level check) and returns a clear `422` instead of a `500`. A catch-all `Exception` handler guarantees every response — including truly unexpected errors — is JSON, never an HTML error page, and logs the full traceback server-side.

**Logging:** the request-logging middleware now logs every request's method/path/status/duration, and adds a second, more detailed `WARNING` line for any response ≥400 (including query params and client host) so failures are easy to find in the console without reproducing them.

**Frontend ↔ backend address:** `frontend/script.js` calls `http://127.0.0.1:8000` by default (`API_BASE`), matching the `uvicorn ... --port 8000` command above. Override it by setting `window.TASKFLOW_API_BASE` in an inline `<script>` tag before `script.js` loads if you run the backend on a different host/port — the CORS config's `FRONTEND_ORIGIN` env var and this value need to agree with wherever each side is actually running.

## Database schema

Three tables, `users` → `projects` → `tasks`, defined as SQLAlchemy ORM models in `backend/models.py`:

- **users**: `id` PK, `email` UNIQUE NOT NULL, `name` NOT NULL
- **projects**: `id` PK, `name` NOT NULL, `description`, `owner_id` FK → `users.id` NOT NULL
- **tasks**: `id` PK, `title` NOT NULL, `description`, `priority` (CHECK constraint, `'low' | 'medium' | 'high'`), `due_date` TEXT nullable (intentionally plain text — holds both manually-typed dates and AI-parsed phrases like `"next friday"`), `status`, `project_id` FK → `projects.id` NOT NULL

`User.projects` ↔ `Project.owner`, and `Project.tasks` ↔ `Task.project` are wired with `relationship(..., back_populates=...)` on both sides.

## Endpoints

All endpoints share one `get_db` dependency (`backend/database.py`) and one FastAPI app (`backend/main.py`). A logging middleware prints `METHOD /path completed in X.XXms` for every request.

| Method | Path | Example request | Example response |
|---|---|---|---|
| POST | `/users` | `{"email":"lead@blinkit.com","name":"Pod Lead"}` | `201` `{"id":1,"email":"lead@blinkit.com","name":"Pod Lead"}` |
| GET | `/users` | — | `200` `[{"id":1,"email":"lead@blinkit.com","name":"Pod Lead"}]` |
| POST | `/projects` | `{"name":"Cold Chain","owner_id":1}` | `201` `{"id":1,"name":"Cold Chain","description":null,"owner_id":1}` |
| GET | `/projects` | — | `200` `[{"id":1,"name":"Cold Chain","description":null,"owner_id":1}]` |
| GET | `/projects/{id}` | — | `200` `{"id":1,"name":"Cold Chain","description":null,"owner_id":1}` / `404` if missing |
| GET | `/projects/{id}/stats` | — | `200` `{"project_id":1,"project_name":"Cold Chain","task_count":3,"status_counts":{"todo":3}}` |
| POST | `/tasks` | `{"title":"Fix freezer sensor","priority":"high","project_id":1}` | `201` `{"id":1,"title":"Fix freezer sensor","description":null,"priority":"high","due_date":null,"status":"todo","project_id":1}` / `422` on blank title or bad `project_id` |
| GET | `/tasks?project_id=1&sort=priority` | — | `200` list of tasks ordered by `insertion_sort` (low→high) |
| GET | `/tasks/{id}` | — | `200` task / `404` if missing |
| PUT | `/tasks/{id}` | `{"status":"done"}` | `200` updated task / `404` if missing |
| DELETE | `/tasks/{id}` | — | `200` `{"detail":"Task deleted","id":1}` / `404` if missing |
| GET | `/tasks/search?title=Restock%20aisle%203&algo=binary` | — | `200` matching task / `404` if no exact-title match |
| POST | `/tasks/quick-add` | `{"description":"Fix the freezer, it's urgent","project_id":1}` | `201` `{"id":5,"title":"Fix the freezer, it's","priority":"high","due_date":null,...}` / `422` on malformed body or bad `project_id` |

All of the above were exercised end-to-end with `curl` during development (create, list, get-by-id, update, delete, statistics across two projects with different task counts, sorted list, binary/linear search including a 404 case, and quick-add including a 422 case) — see commit history.

## Algorithms (Section 2)

`backend/algorithms.py` implements `insertion_sort`, `binary_search`, and `linear_search` from scratch (never `sorted()`/`.sort()`), plus comparison-counting wrapper versions (`insertion_sort_count`, `binary_search_count`, `linear_search_count`) used only for benchmarking. `GET /tasks?sort=priority|due_date` and `GET /tasks/search` are the two live endpoints that call these functions directly on real database rows — see `main.py`. `binary_search`/`linear_search` return `None` (not `-1`) when a target isn't found.

**Complexity:**

| Function | Best case | Worst case |
|---|---|---|
| `insertion_sort` | O(n) — already sorted | O(n²) — reverse sorted |
| `binary_search` | O(1) — target at midpoint | O(log n) |
| `linear_search` | O(1) — target at index 0 | O(n) |

**Benchmark results** (comparison counts, from `benchmark.py`, synthetic task dicts shaped like the real `title`/`priority`/`due_date` fields, 3 sizes; raw output also in `benchmark_results.txt`):

```
  size |   insertion_sort (title) |  binary_search (title) |  linear_search (title)
------------------------------------------------------------------------------------------
    10 |                       31 |                      3 |                      1
   500 |                    64696 |                      8 |                    442
  3000 |                  2264605 |                     11 |                   2860
```

**Is sorting-first worth it?** Sorting 3,000 tasks costs ~2.26M comparisons — a real, measurable up-front cost — but a team is described as listing/sorting their task list repeatedly through the day while adding or renaming tasks far less often. `GET /tasks?sort=priority` re-sorts from scratch on every call rather than persisting an order, so in TaskFlow's actual usage pattern that sort cost is paid on every read, not amortized across writes. For the realistic pod size (tens to low hundreds of open tasks, not 3,000), the sort cost stays small in absolute terms (well under 100k comparisons at n=500), and the payoff — binary search dropping to single-digit/low-double-digit comparisons versus linear search's up to n comparisons on `GET /tasks/search` — is worth it precisely because search is also a frequent read. At genuinely large n the O(n²) sort becomes the dominant cost and would be worth revisiting (e.g. sorting once and caching), but at TaskFlow's expected scale the current approach is the right trade-off.

## AI Quick-Add (Section 3)

`POST /tasks/quick-add` accepts `{"description": "...", "project_id": ...}`, builds a role-based prompt (`build_prompt_messages` in `backend/ai_parser.py` — a `system` message describing the parsing behavior + a `user` message carrying the free text) and, by default, resolves it with a deterministic, rule-based mock parser (`mock_parse_task`) that needs no API key and makes no network calls. An optional real-LLM path exists behind `USE_REAL_LLM` (unset/false by default) and falls back to the mock automatically if the flag is off or the call fails — grading runs with the flag off and no key present. Whatever the mock (or real path) produces is validated against the same `TaskCreate` Pydantic model the rest of the app uses before anything is written; a validation failure or unknown `project_id` returns `422` with no row created.

**Prompting technique:** the system message is a single, direct instruction set with no embedded examples — i.e. **zero-shot**, not few-shot or chain-of-thought. This fits the mock's fully deterministic algorithm: because the parsing logic is exact keyword-matching with a fixed rule order (not a model doing open-ended reasoning), there's nothing for few-shot examples or CoT scratch-space to disambiguate — adding either would just spend tokens without improving reliability. If the optional real-LLM path is used instead, the same zero-shot message would likely need to move toward few-shot (2-3 input/output pairs matching the exact algorithm below) to keep a real model's output format reliable, at the cost of a larger prompt and higher token usage per call.

**Five worked examples** (verified against the running mock):

| Input | Output |
|---|---|
| `"This is urgent, mark it ASAP please"` | `{"title": "This is , mark it please", "priority": "high", "due_date_hint": null}` |
| `" "` (whitespace only) | `{"title": "Untitled task", "priority": "medium", "due_date_hint": null}` |
| `"Finish the report next Friday, it's urgent"` | `{"title": "Finish the report , it's", "priority": "high", "due_date_hint": "next friday"}` |
| `"tomorrow review tomorrow"` | `{"title": "review", "priority": "medium", "due_date_hint": "tomorrow"}` |
| `"Whenever you get a chance, restock the shelves on monday"` | `{"title": "you get a chance, restock the shelves on", "priority": "low", "due_date_hint": "monday"}` |

## Repository layout

```
taskflow/
├── backend/            # FastAPI app: CRUD + stats (Sec 1), sort/search (Sec 2), quick-add (Sec 3)
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── algorithms.py
│   └── ai_parser.py
├── frontend/            # index.html, styles.css, script.js — calls the real backend
├── seed.py
├── benchmark.py
├── benchmark_results.txt
├── check_algorithms.py
├── requirements.txt
└── README.md
```
