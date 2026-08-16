# TaskFlow

TaskFlow is a simple task management web application built as a full-stack project. It lets users create and manage projects and tasks, search and sort tasks, view project statistics, and add tasks using a quick-add feature.

The project uses FastAPI and SQLAlchemy for the backend and HTML, CSS, and JavaScript for the frontend.

## Project Structure


taskflow/
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── algorithms.py
│   └── ai_parser.py
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── script.js
├── benchmark.py
├── benchmark_results.txt
├── check_algorithms.py
├── seed.py
├── requirements.txt
└── README.md


## Setup

First, clone the repository and open the project folder:

```bash
git clone https://github.com/AadityaSingh-arch/MASAI_Capstone_Project.git
cd taskflow
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it.


```bash
venv\Scripts\activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

## Running the App

Start the backend from the project root:

```bash
uvicorn backend.main:app --reload --port 8000
```

Then open another terminal, go into the frontend folder, and start the frontend server:

```bash
cd frontend
python -m http.server 5500
```

Now open the following in your browser:

```text
http://127.0.0.1:5500
```

The backend runs at:

```text
http://127.0.0.1:8000
```

FastAPI's API documentation can be viewed at:

```text
http://127.0.0.1:8000/docs
```

The SQLite database and its tables are created automatically when the backend starts.

## API Endpoints

The main API endpoints are listed below.

| Category       | Method | Path                           |
| -------------- | ------ | ------------------------------ |
| Create User    | POST   | `/users`                       |
| List Users     | GET    | `/users`                       |
| Create Project | POST   | `/projects`                    |
| List Projects  | GET    | `/projects`                    |
| Get Project    | GET    | `/projects/{project_id}`       |
| Statistics     | GET    | `/projects/{project_id}/stats` |
| Create Task    | POST   | `/tasks`                       |
| List Tasks     | GET    | `/tasks`                       |
| Sorted List    | GET    | `/tasks?sort=priority`         |
| Get Task       | GET    | `/tasks/{task_id}`             |
| Update Task    | PUT    | `/tasks/{task_id}`             |
| Delete Task    | DELETE | `/tasks/{task_id}`             |
| Search         | GET    | `/tasks/search`                |
| Quick-Add      | POST   | `/tasks/quick-add`             |

### Create

```http
POST /tasks
```

Request:

```json
{
  "title": "Fix freezer sensor",
  "description": "Inspect temperature sensor",
  "priority": "high",
  "due_date": "2026-08-20",
  "status": "todo",
  "project_id": 1
}
```

Response:

```json
{
  "id": 1,
  "title": "Fix freezer sensor",
  "description": "Inspect temperature sensor",
  "priority": "high",
  "due_date": "2026-08-20",
  "status": "todo",
  "project_id": 1
}
```

### List

```http
GET /tasks?project_id=1
```

Response:

```json
[
  {
    "id": 1,
    "title": "Fix freezer sensor",
    "priority": "high",
    "status": "todo",
    "project_id": 1
  }
]
```

### Get by ID

```http
GET /tasks/1
```

Response:

```json
{
  "id": 1,
  "title": "Fix freezer sensor",
  "priority": "high",
  "status": "todo",
  "project_id": 1
}
```

### Update

```http
PUT /tasks/1
```

Request:

```json
{
  "status": "done"
}
```

Response:

```json
{
  "id": 1,
  "title": "Fix freezer sensor",
  "priority": "high",
  "status": "done",
  "project_id": 1
}
```

### Delete

```http
DELETE /tasks/1
```

Response:

```json
{
  "detail": "Task deleted",
  "id": 1
}
```

### Statistics

```http
GET /projects/1/stats
```

Response:

```json
{
  "project_id": 1,
  "project_name": "Cold Chain",
  "task_count": 3,
  "status_counts": {
    "todo": 2,
    "done": 1
  }
}
```

### Sorted List

Tasks can be sorted by priority or due date.

```http
GET /tasks?project_id=1&sort=priority
```

Response:

```json
[
  {
    "id": 2,
    "title": "Update documentation",
    "priority": "low",
    "status": "todo"
  },
  {
    "id": 1,
    "title": "Fix freezer sensor",
    "priority": "high",
    "status": "todo"
  }
]
```

The sorting is handled by the hand-written insertion sort in `backend/algorithms.py`.

### Search

```http
GET /tasks/search?title=Fix%20freezer%20sensor&algo=binary
```

Response:

```json
{
  "id": 1,
  "title": "Fix freezer sensor",
  "priority": "high",
  "status": "todo"
}
```

Both binary search and linear search are supported.

### Quick-Add

```http
POST /tasks/quick-add
```

Request:

```json
{
  "description": "Finish the report next Friday, it's urgent",
  "project_id": 1
}
```

Response:

```json
{
  "id": 5,
  "title": "Finish the report, it's",
  "priority": "high",
  "due_date": "next friday",
  "status": "todo"
}
```

## Algorithms

The required algorithms are implemented manually in `backend/algorithms.py`.

### Insertion Sort

Insertion sort is used for the task sorting functionality.

* Best case: **O(n)**
* Average case: **O(n²)**
* Worst case: **O(n²)**
* Space: **O(1)**

### Binary Search

Binary search is used for searching task titles after sorting them.

* Best case: **O(1)**
* Average case: **O(log n)**
* Worst case: **O(log n)**
* Space: **O(1)**

### Linear Search

Linear search is included as a comparison with binary search.

* Best case: **O(1)**
* Average case: **O(n)**
* Worst case: **O(n)**
* Space: **O(1)**

### Benchmark Results

The benchmark measures the number of comparisons made by each algorithm.

| Input Size | Insertion Sort | Binary Search | Linear Search |
| ---------: | -------------: | ------------: | ------------: |
|         10 |             31 |             3 |             1 |
|        500 |         64,696 |             8 |           442 |
|      3,000 |      2,264,605 |            11 |         2,860 |

These results match the expected behavior: insertion sort becomes much more expensive as the input grows, while binary search increases very slowly.

Run the benchmark with:

```bash
python benchmark.py
```

The algorithm checks can be run with:

```bash
python check_algorithms.py
```

## AI Quick-Add

The Quick-Add feature is designed to turn a short natural-language description into a task.

For example:

> Finish the report next Friday, it's urgent

can be interpreted as:

```text
Title: Finish the report
Priority: High
Due date: Next Friday
```

The required mock parser works completely locally. It does not need an API key, internet connection, or paid AI service.

The parser looks for common priority and date phrases such as:

* `urgent`
* `ASAP`
* `whenever`
* `today`
* `tomorrow`
* weekdays
* `next week`

## Prompting Technique

The project uses a zero-shot prompting approach for the quick-add feature.

The system instructions explain what information needs to be extracted from the user's text. No example conversations are required for the basic parser.

This approach was chosen because the required parser is deterministic and rule-based. Keeping the instructions simple makes the result predictable and avoids depending on an external AI service.

A real LLM implementation can be added optionally, but it is disabled by default and is not required to run the project.

## Five Quick-Add Examples

### Example 1

Input:

```text
This is urgent, mark it ASAP please
```

Result:

```text
Priority: high
Due date: none
```

### Example 2

Input:

```text
Finish the report tomorrow
```

Result:

```text
Priority: medium
Due date: tomorrow
```

### Example 3

Input:

```text
Finish the report next Friday, it's urgent
```

Result:

```text
Priority: high
Due date: next friday
```

## Git Workflow

The project was developed using a feature-branch workflow. The repository contains multiple commits on a feature branch followed by a merge back into `main`.

The history can be checked using:

```bash
git log --graph --all --oneline
```

## Requirements

* Python 3
* Packages listed in `requirements.txt`
* No paid API or subscription
* No API key required for the grading version

Everything required to run and test the project is contained in this repository.
