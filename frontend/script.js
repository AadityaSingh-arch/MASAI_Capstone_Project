/**
 * TaskFlow dashboard logic.
 *
 * - Talks to the real Section 1 backend over the Fetch API (no mock data).
 * - Renders the task list with createElement/appendChild + textContent only
 *   (never innerHTML for anything that came from user input).
 * - Caches the current task list in localStorage on every change, and
 *   renders from that cache first on page load while the live fetch is in
 *   flight, so the page never shows a blank list while data loads.
 * - The Add Task / Quick-add forms stay disabled until initialization
 *   (loading projects + picking an active one) has actually completed.
 */

// Must match whatever host:port the backend is actually running on
// (see README "Running the app"). Override by setting
// window.TASKFLOW_API_BASE in an inline <script> before this file loads.
const API_BASE = window.TASKFLOW_API_BASE || "http://127.0.0.1:8000";
const CACHE_KEY = "taskflow:cachedTasks";
const PROJECT_CACHE_KEY = "taskflow:activeProjectId";
const VALID_PRIORITIES = ["low", "medium", "high"];
const VALID_STATUSES = ["todo", "in_progress", "done"];
const DUE_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

const state = {
  projects: [],
  activeProjectId: null,
  tasks: [],
  searchActive: false,
  initialized: false,
  pendingRequestCount: 0,
};

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const el = {
  initBanner: document.getElementById("init-banner"),
  initBannerMessage: document.getElementById("init-banner-message"),
  initRetryBtn: document.getElementById("init-retry-btn"),
  loadingBar: document.getElementById("loading-bar"),
  projectSelect: document.getElementById("project-select"),
  sortSelect: document.getElementById("sort-select"),
  taskList: document.getElementById("task-list"),
  emptyState: document.getElementById("empty-state"),
  addForm: document.getElementById("add-task-form"),
  addSubmit: document.getElementById("add-task-submit"),
  titleInput: document.getElementById("task-title"),
  titleError: document.getElementById("title-error"),
  dueInput: document.getElementById("task-due"),
  dueError: document.getElementById("due-error"),
  priorityInput: document.getElementById("task-priority"),
  quickAddForm: document.getElementById("quick-add-form"),
  quickAddSubmit: document.getElementById("quick-add-submit"),
  quickAddInput: document.getElementById("quick-add-text"),
  searchInput: document.getElementById("search-input"),
  searchAlgo: document.getElementById("search-algo"),
  searchBtn: document.getElementById("search-btn"),
  searchClearBtn: document.getElementById("search-clear-btn"),
  statTotal: document.getElementById("stat-total"),
  statTodo: document.getElementById("stat-todo"),
  statInProgress: document.getElementById("stat-in_progress"),
  statDone: document.getElementById("stat-done"),
  toastContainer: document.getElementById("toast-container"),
};

// ---------------------------------------------------------------------------
// Toasts / loading indicator
// ---------------------------------------------------------------------------
function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.textContent = message;
  el.toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

function setLoading(isLoading) {
  state.pendingRequestCount += isLoading ? 1 : -1;
  if (state.pendingRequestCount < 0) state.pendingRequestCount = 0;
  el.loadingBar.hidden = state.pendingRequestCount === 0;
}

function setFormsEnabled(enabled) {
  [el.titleInput, el.dueInput, el.priorityInput, el.addSubmit, el.quickAddInput, el.quickAddSubmit].forEach(
    (node) => {
      node.disabled = !enabled;
    }
  );
}

function showInitError(message) {
  el.initBannerMessage.textContent = message;
  el.initBanner.hidden = false;
}

function hideInitError() {
  el.initBanner.hidden = true;
  el.initBannerMessage.textContent = "";
}

// ---------------------------------------------------------------------------
// localStorage cache helpers
// ---------------------------------------------------------------------------
function readCache() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (err) {
    console.warn("Cached task list was invalid JSON — ignoring it.", err);
    localStorage.removeItem(CACHE_KEY);
    return [];
  }
}

function writeCache(tasks) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(tasks));
  } catch (err) {
    console.warn("Could not write task cache to localStorage:", err);
  }
}

/** Returns a valid cached project id (number, present in `projects`), or
 * null — and clears the cache entry if what's stored doesn't check out. */
function readValidCachedProjectId(projects) {
  const raw = localStorage.getItem(PROJECT_CACHE_KEY);
  if (raw === null) return null;
  const id = Number(raw);
  const isValid = Number.isInteger(id) && projects.some((p) => p.id === id);
  if (!isValid) {
    console.warn(`Cached project id "${raw}" is invalid or no longer exists — clearing it.`);
    localStorage.removeItem(PROJECT_CACHE_KEY);
    return null;
  }
  return id;
}

// ---------------------------------------------------------------------------
// Rendering (DOM APIs only — no innerHTML for user-provided values)
// ---------------------------------------------------------------------------
function renderTasks(tasks) {
  el.taskList.textContent = ""; // clear previous render

  if (!tasks || tasks.length === 0) {
    el.emptyState.hidden = false;
    return;
  }
  el.emptyState.hidden = true;

  tasks.forEach((task) => {
    el.taskList.appendChild(buildTaskItem(task));
  });
}

function buildTaskItem(task) {
  const li = document.createElement("li");
  li.className = `task-item task-item--${task.priority || "medium"}`;
  li.dataset.taskId = task.id;

  const main = document.createElement("div");
  main.className = "task-item__main";

  const title = document.createElement("span");
  title.className = "task-item__title";
  title.textContent = task.title; // textContent: safe for user-provided text
  main.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "task-item__meta";

  const priorityBadge = document.createElement("span");
  priorityBadge.textContent = `Priority: ${task.priority}`;
  meta.appendChild(priorityBadge);

  if (task.due_date) {
    const due = document.createElement("span");
    due.textContent = `Due: ${task.due_date}`;
    meta.appendChild(due);
  }

  const status = document.createElement("span");
  status.textContent = `Status: ${task.status}`;
  meta.appendChild(status);

  main.appendChild(meta);
  li.appendChild(main);

  const actions = document.createElement("div");
  actions.className = "task-item__actions";

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.textContent = "Edit";
  editBtn.addEventListener("click", () => toggleEditForm(li, task));
  actions.appendChild(editBtn);

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "delete-btn";
  deleteBtn.textContent = "Delete";
  deleteBtn.addEventListener("click", () => handleDelete(task.id, deleteBtn));
  actions.appendChild(deleteBtn);

  li.appendChild(actions);
  return li;
}

function toggleEditForm(li, task) {
  const existing = li.querySelector(".task-item__edit-form");
  if (existing) {
    existing.remove();
    return;
  }

  const form = document.createElement("form");
  form.className = "task-item__edit-form";
  form.style.display = "flex";
  form.style.gap = "8px";
  form.style.flexWrap = "wrap";
  form.style.marginTop = "10px";
  form.style.width = "100%";

  const titleInput = document.createElement("input");
  titleInput.type = "text";
  titleInput.value = task.title;
  titleInput.required = true;

  const dueInput = document.createElement("input");
  dueInput.type = "date";
  // Only pre-fill if the stored value is already a real ISO date (e.g. not
  // an AI-parsed phrase like "next friday", which the date input can't show).
  dueInput.value = DUE_DATE_PATTERN.test(task.due_date || "") ? task.due_date : "";

  const prioritySelect = document.createElement("select");
  VALID_PRIORITIES.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    if (p === task.priority) opt.selected = true;
    prioritySelect.appendChild(opt);
  });

  const statusSelect = document.createElement("select");
  VALID_STATUSES.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    if (s === task.status) opt.selected = true;
    statusSelect.appendChild(opt);
  });

  const errorSpan = document.createElement("span");
  errorSpan.className = "field__error";
  errorSpan.setAttribute("role", "alert");
  errorSpan.style.flexBasis = "100%";

  const saveBtn = document.createElement("button");
  saveBtn.type = "submit";
  saveBtn.className = "btn btn--primary";
  saveBtn.textContent = "Save";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "btn btn--ghost";
  cancelBtn.textContent = "Cancel";
  cancelBtn.addEventListener("click", () => form.remove());

  form.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    errorSpan.textContent = "";

    const trimmedTitle = titleInput.value.trim();
    if (!trimmedTitle) {
      errorSpan.textContent = "Title is required.";
      titleInput.focus();
      return;
    }
    if (dueInput.value && !DUE_DATE_PATTERN.test(dueInput.value)) {
      errorSpan.textContent = "Due date must be a valid date.";
      return;
    }
    if (!VALID_PRIORITIES.includes(prioritySelect.value)) {
      errorSpan.textContent = "Invalid priority.";
      return;
    }
    if (!VALID_STATUSES.includes(statusSelect.value)) {
      errorSpan.textContent = "Invalid status.";
      return;
    }

    saveBtn.disabled = true;
    cancelBtn.disabled = true;
    // Note: project_id is intentionally omitted from this payload so the
    // task's project assignment is preserved untouched during an edit.
    const ok = await handleUpdate(task.id, {
      title: trimmedTitle,
      due_date: dueInput.value || null,
      priority: prioritySelect.value,
      status: statusSelect.value,
    });
    if (!ok) {
      saveBtn.disabled = false;
      cancelBtn.disabled = false;
      errorSpan.textContent = state.lastErrorMessage || "Could not save changes.";
    }
  });

  [titleInput, dueInput, prioritySelect, statusSelect, saveBtn, cancelBtn, errorSpan].forEach((node) => {
    form.appendChild(node);
  });

  li.appendChild(form);
}

function renderStats(stats) {
  if (!stats) {
    el.statTotal.textContent = "–";
    el.statTodo.textContent = "–";
    el.statInProgress.textContent = "–";
    el.statDone.textContent = "–";
    return;
  }
  el.statTotal.textContent = stats.task_count ?? 0;
  const counts = stats.status_counts || {};
  el.statTodo.textContent = counts.todo ?? 0;
  el.statInProgress.textContent = counts.in_progress ?? 0;
  el.statDone.textContent = counts.done ?? 0;
}

function renderProjectOptions() {
  el.projectSelect.textContent = "";
  state.projects.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.name;
    el.projectSelect.appendChild(opt);
  });
  if (state.activeProjectId) {
    el.projectSelect.value = state.activeProjectId;
  }
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------
/**
 * Wraps fetch with:
 *  - correct Content-Type on every request with a body
 *  - a global loading indicator for the duration of the call
 *  - structured errors: err.type is 'network' | 'validation' | 'not_found' | 'server' | 'client'
 *  - the backend's actual message surfaced on err.detail (never a generic string)
 *  - full detail logged to the console on every failure
 */
async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`;
  setLoading(true);
  let res;
  try {
    res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (networkErr) {
    setLoading(false);
    console.error(`Network error calling ${options.method || "GET"} ${url}:`, networkErr);
    const err = new Error(
      "Could not reach the TaskFlow backend. Is it running, and does the API base URL match?"
    );
    err.type = "network";
    throw err;
  }
  setLoading(false);

  if (!res.ok) {
    let body = null;
    try {
      body = await res.json();
    } catch (parseErr) {
      /* error body wasn't JSON — fall through with body = null */
    }
    const detail =
      (body && (formatBackendErrors(body) || body.detail)) || res.statusText || "Request failed.";
    console.error(`${options.method || "GET"} ${url} -> ${res.status}`, { body, detail });

    const err = new Error(detail);
    err.status = res.status;
    err.detail = detail;
    err.type = res.status === 404 ? "not_found" : res.status === 422 ? "validation" : res.status >= 500 ? "server" : "client";
    throw err;
  }

  if (res.status === 204) return null;
  try {
    return await res.json();
  } catch (err) {
    return null;
  }
}

/** Flattens the {"detail": "...", "errors": [{"field":..,"message":..}]}
 * shape the backend's validation handler returns into one readable string. */
function formatBackendErrors(body) {
  if (!body || !Array.isArray(body.errors) || body.errors.length === 0) return null;
  return body.errors.map((e) => (e.field ? `${e.field}: ${e.message}` : e.message)).join("; ");
}

async function loadStats(projectId) {
  try {
    const stats = await apiFetch(`/projects/${projectId}/stats`);
    renderStats(stats);
  } catch (err) {
    // Missing/failed stats shouldn't break the rest of the UI.
    renderStats(null);
  }
}

async function loadTasks() {
  if (!state.activeProjectId) return;
  const sort = el.sortSelect.value;
  const qs = new URLSearchParams({ project_id: state.activeProjectId });
  if (sort) qs.set("sort", sort);

  try {
    const tasks = await apiFetch(`/tasks?${qs.toString()}`);
    state.tasks = tasks;
    writeCache(tasks);
    if (!state.searchActive) {
      renderTasks(tasks);
    }
    await loadStats(state.activeProjectId);
  } catch (err) {
    showToast(`Could not load tasks: ${err.message}`, "error");
  }
}

// ---------------------------------------------------------------------------
// Client-side validation
// ---------------------------------------------------------------------------
function validateTitleField() {
  const value = el.titleInput.value.trim();
  if (!value) {
    el.titleError.textContent = "Title is required.";
    return false;
  }
  el.titleError.textContent = "";
  return true;
}

function validateDueDateField() {
  const value = el.dueInput.value;
  if (value && !DUE_DATE_PATTERN.test(value)) {
    el.dueError.textContent = "Enter a valid date.";
    return false;
  }
  el.dueError.textContent = "";
  return true;
}

el.titleInput.addEventListener("input", () => {
  if (el.titleInput.value.trim()) el.titleError.textContent = "";
});
el.dueInput.addEventListener("change", validateDueDateField);

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------
el.addForm.addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const titleOk = validateTitleField();
  const dueOk = validateDueDateField();
  if (!titleOk || !dueOk) return;

  if (!state.activeProjectId) {
    el.titleError.textContent = "No active project — cannot create a task yet.";
    return;
  }
  if (!VALID_PRIORITIES.includes(el.priorityInput.value)) {
    el.titleError.textContent = "Invalid priority selected.";
    return;
  }

  const payload = {
    title: el.titleInput.value.trim(),
    due_date: el.dueInput.value || null,
    priority: el.priorityInput.value,
    status: "todo",
    project_id: state.activeProjectId,
  };

  el.addSubmit.disabled = true;
  try {
    await apiFetch("/tasks", { method: "POST", body: JSON.stringify(payload) });
    el.addForm.reset();
    el.priorityInput.value = "medium";
    el.titleError.textContent = "";
    el.dueError.textContent = "";
    showToast("Task created.");
    await loadTasks();
  } catch (err) {
    // Show the backend's actual validation message, not a generic one.
    el.titleError.textContent = err.detail || err.message || "Could not save task.";
  } finally {
    el.addSubmit.disabled = false;
  }
});

el.quickAddForm.addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const description = el.quickAddInput.value.trim();
  if (!description) return;
  if (!state.activeProjectId) {
    showToast("No active project — cannot quick-add yet.", "error");
    return;
  }

  el.quickAddSubmit.disabled = true;
  try {
    await apiFetch("/tasks/quick-add", {
      method: "POST",
      body: JSON.stringify({ description, project_id: state.activeProjectId }),
    });
    el.quickAddForm.reset();
    showToast("Task parsed and added.");
    await loadTasks();
  } catch (err) {
    showToast(`Quick-add failed: ${err.detail || err.message}`, "error");
  } finally {
    el.quickAddSubmit.disabled = false;
  }
});

async function handleDelete(taskId, triggerBtn) {
  if (!window.confirm("Delete this task? This cannot be undone.")) return;
  if (triggerBtn) triggerBtn.disabled = true;
  try {
    await apiFetch(`/tasks/${taskId}`, { method: "DELETE" });
    showToast("Task deleted.");
    await loadTasks();
  } catch (err) {
    showToast(`Could not delete task: ${err.detail || err.message}`, "error");
    if (triggerBtn) triggerBtn.disabled = false;
  }
}

/** Returns true on success, false on failure (caller re-enables its own
 * form controls either way and reads state.lastErrorMessage on failure). */
async function handleUpdate(taskId, updates) {
  try {
    await apiFetch(`/tasks/${taskId}`, {
      method: "PUT",
      body: JSON.stringify(updates),
    });
    showToast("Task updated.");
    await loadTasks();
    return true;
  } catch (err) {
    state.lastErrorMessage = err.detail || err.message;
    console.error("Update failed:", err);
    return false;
  }
}

el.sortSelect.addEventListener("change", () => {
  loadTasks();
});

el.projectSelect.addEventListener("change", () => {
  const id = Number(el.projectSelect.value);
  if (!Number.isInteger(id) || !state.projects.some((p) => p.id === id)) {
    console.warn(`Selected project id "${el.projectSelect.value}" is invalid — ignoring.`);
    return;
  }
  state.activeProjectId = id;
  localStorage.setItem(PROJECT_CACHE_KEY, String(id));
  state.searchActive = false;
  loadTasks();
});

el.searchBtn.addEventListener("click", async () => {
  const title = el.searchInput.value.trim();
  if (!title) return;
  const qs = new URLSearchParams({ title, algo: el.searchAlgo.value });
  el.searchBtn.disabled = true;
  try {
    const task = await apiFetch(`/tasks/search?${qs.toString()}`);
    state.searchActive = true;
    renderTasks([task]);
  } catch (err) {
    state.searchActive = true;
    if (err.type === "not_found") {
      el.taskList.textContent = "";
      el.emptyState.hidden = false;
      el.emptyState.textContent = `No task found with title "${title}".`;
    } else {
      showToast(`Search failed: ${err.detail || err.message}`, "error");
    }
  } finally {
    el.searchBtn.disabled = false;
  }
});

el.searchClearBtn.addEventListener("click", () => {
  state.searchActive = false;
  el.searchInput.value = "";
  el.emptyState.textContent = "No tasks yet — add one above to get started.";
  renderTasks(state.tasks);
});

el.initRetryBtn.addEventListener("click", () => {
  hideInitError();
  init();
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
async function init() {
  setFormsEnabled(false);
  hideInitError();

  // Render from cache immediately so the page never shows blank while the
  // live request is in flight.
  const cached = readCache();
  if (cached.length > 0) {
    renderTasks(cached);
  }

  try {
    const projects = await apiFetch("/projects");
    state.projects = projects || [];

    if (state.projects.length === 0) {
      // The backend creates a default project on its own startup, so this
      // should not normally happen — but handle it explicitly rather than
      // leaving activeProjectId null and forms silently broken.
      showInitError(
        "No projects exist yet and none could be loaded automatically. " +
        "Confirm the backend is running and reachable, then retry."
      );
      return;
    }

    renderProjectOptions();

    const cachedProjectId = readValidCachedProjectId(state.projects);
    state.activeProjectId = cachedProjectId ?? state.projects[0].id;
    el.projectSelect.value = state.activeProjectId;
    localStorage.setItem(PROJECT_CACHE_KEY, String(state.activeProjectId));

    state.initialized = true;
    setFormsEnabled(true);

    await loadTasks();
  } catch (err) {
    console.error("Failed to initialize TaskFlow:", err);
    showInitError(
      err.type === "network"
        ? "Could not reach the TaskFlow backend. Confirm it's running at " +
          `${API_BASE} and retry.`
        : `Initialization failed: ${err.detail || err.message}`
    );
  }
}

init();
