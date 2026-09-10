const elements = {
  accessPanel: document.querySelector("#access-panel"),
  accessForm: document.querySelector("#access-form"),
  apiKey: document.querySelector("#api-key"),
  accessError: document.querySelector("#access-error"),
  workspace: document.querySelector("#workspace"),
  refresh: document.querySelector("#refresh"),
  lastUpdated: document.querySelector("#last-updated"),
  calls: document.querySelector("#calls"),
  candidates: document.querySelector("#candidates"),
  actions: document.querySelector("#actions"),
  callCount: document.querySelector("#call-count"),
  ticketCount: document.querySelector("#ticket-count"),
  candidateCount: document.querySelector("#candidate-count"),
  actionCount: document.querySelector("#action-count"),
  healthDot: document.querySelector("#health-dot"),
  healthLabel: document.querySelector("#health-label"),
};

const state = { key: sessionStorage.getItem("faultbridgeInternalKey") || "" };

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatLabel(value) {
  return String(value || "unknown")
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}

function createElement(tag, className, content) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (content !== undefined) element.textContent = content;
  return element;
}

function renderEmpty(container, message, tableColumns = null) {
  if (tableColumns) {
    const row = document.createElement("tr");
    const cell = createElement("td", "empty-state", message);
    cell.colSpan = tableColumns;
    row.append(cell);
    container.replaceChildren(row);
    return;
  }
  container.replaceChildren(createElement("div", "empty-state", message));
}

function renderCalls(calls) {
  if (!calls.length) {
    renderEmpty(elements.calls, "No calls recorded yet", 5);
    return;
  }
  const rows = calls.map((call) => {
    const row = document.createElement("tr");
    const received = createElement("td", "time-cell", formatTime(call.created_at));
    const location = document.createElement("td");
    const area = createElement("strong", "", call.area || "Area unavailable");
    const cell = createElement("small", "", call.cell_id || "Cell unavailable");
    location.append(area, cell);
    const language = createElement("td", "", call.language_pair || "—");
    const issue = createElement("td", "", formatLabel(call.symptom));
    const outcome = document.createElement("td");
    outcome.append(createElement("span", "outcome-pill", formatLabel(call.outcome)));
    row.append(received, location, language, issue, outcome);
    return row;
  });
  elements.calls.replaceChildren(...rows);
}

function recordCard(title, metadata, timestamp) {
  const card = createElement("article", "record-card");
  const content = document.createElement("div");
  content.append(createElement("strong", "", title), createElement("small", "", metadata));
  card.append(content, createElement("time", "", formatTime(timestamp)));
  return card;
}

function renderCandidates(candidates) {
  if (!candidates.length) {
    renderEmpty(elements.candidates, "No candidate incidents");
    return;
  }
  elements.candidates.replaceChildren(...candidates.map((item) => recordCard(
    `${item.cell_id || "Unknown cell"} · ${formatLabel(item.symptom)}`,
    `${formatLabel(item.status)} · ${item.evidence_count || 0} distinct callers`,
    item.updated_at || item.created_at,
  )));
}

function renderActions(actions) {
  if (!actions.length) {
    renderEmpty(elements.actions, "No actions queued");
    return;
  }
  elements.actions.replaceChildren(...actions.map((item) => {
    const title = item.amount_mb
      ? `${item.amount_mb} MB compensation`
      : `Callback · ${formatLabel(item.trigger)}`;
    return recordCard(
      title,
      `${formatLabel(item.status)} · ${item.attempt_count || 0} delivery attempts`,
      item.updated_at || item.created_at,
    );
  }));
}

function renderDashboard(data) {
  const calls = Array.isArray(data.calls) ? data.calls : [];
  const tickets = Array.isArray(data.tickets) ? data.tickets : [];
  const candidates = Array.isArray(data.candidate_incidents) ? data.candidate_incidents : [];
  const compensation = Array.isArray(data.compensation_commands) ? data.compensation_commands : [];
  const callbacks = Array.isArray(data.callback_commands) ? data.callback_commands : [];
  const actions = [...compensation, ...callbacks];
  elements.callCount.textContent = calls.length;
  elements.ticketCount.textContent = tickets.filter((item) => item.status === "open").length;
  elements.candidateCount.textContent = candidates.length;
  elements.actionCount.textContent = actions.filter((item) => item.status === "queued").length;
  renderCalls(calls);
  renderCandidates(candidates);
  renderActions(actions);
  elements.lastUpdated.textContent = `Updated ${new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date())}`;
}

async function loadDashboard() {
  elements.refresh.disabled = true;
  elements.refresh.textContent = "Refreshing…";
  elements.accessError.textContent = "";
  try {
    const response = await fetch("/internal/dashboard", {
      headers: { "X-Internal-API-Key": state.key },
      cache: "no-store",
    });
    let data = null;
    try {
      data = await response.json();
    } catch {
      // Use the status-specific message below when no JSON body is available.
    }
    if (!response.ok) {
      const message = response.status === 401
        ? "The internal access key is not valid."
        : data?.detail || "The operations data is unavailable.";
      throw new Error(message);
    }
    if (!data || typeof data !== "object") throw new Error("The operations data could not be read.");
    renderDashboard(data);
    elements.accessPanel.hidden = true;
    elements.workspace.hidden = false;
    sessionStorage.setItem("faultbridgeInternalKey", state.key);
  } finally {
    elements.refresh.disabled = false;
    elements.refresh.textContent = "Refresh data";
  }
}

async function checkHealth() {
  try {
    const response = await fetch("/health/ready", { cache: "no-store" });
    if (!response.ok) throw new Error();
    elements.healthDot.classList.add("ready");
    elements.healthLabel.textContent = "Systems ready";
  } catch {
    elements.healthDot.classList.remove("ready");
    elements.healthLabel.textContent = "Service unavailable";
  }
}

elements.apiKey.value = state.key;
elements.accessForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  state.key = elements.apiKey.value.trim();
  try {
    await loadDashboard();
  } catch (error) {
    elements.accessError.textContent = error.message;
    sessionStorage.removeItem("faultbridgeInternalKey");
  }
});
elements.refresh.addEventListener("click", () => {
  loadDashboard().catch((error) => {
    elements.lastUpdated.textContent = error.message;
  });
});
checkHealth();
if (state.key) {
  loadDashboard().catch(() => {
    sessionStorage.removeItem("faultbridgeInternalKey");
    elements.apiKey.value = "";
  });
}
