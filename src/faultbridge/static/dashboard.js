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
  inspector: document.querySelector("#call-inspector"),
  closeInspector: document.querySelector("#close-inspector"),
  inspectorCallId: document.querySelector("#inspector-call-id"),
  inspectorLoading: document.querySelector("#inspector-loading"),
  inspectorContent: document.querySelector("#inspector-content"),
  inspectorLocation: document.querySelector("#inspector-location"),
  inspectorLanguage: document.querySelector("#inspector-language"),
  inspectorIssue: document.querySelector("#inspector-issue"),
  inspectorOutcome: document.querySelector("#inspector-outcome"),
  inspectorTranscript: document.querySelector("#inspector-transcript"),
  inspectorResponse: document.querySelector("#inspector-response"),
  inspectorError: document.querySelector("#inspector-error"),
  eventCount: document.querySelector("#event-count"),
  eventTimeline: document.querySelector("#event-timeline"),
};

const state = {
  key: sessionStorage.getItem("faultbridgeInternalKey") || "",
  inspectorRequest: null,
};

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
    renderEmpty(elements.calls, "No calls recorded yet", 6);
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
    const review = document.createElement("td");
    review.className = "review-cell";
    const reviewButton = createElement("button", "trace-button", "Review trace");
    reviewButton.type = "button";
    reviewButton.setAttribute("aria-label", `Review decision trace for ${call.area || "this call"}`);
    reviewButton.addEventListener("click", () => openCallInspector(call));
    review.append(reviewButton);
    row.append(received, location, language, issue, outcome, review);
    return row;
  });
  elements.calls.replaceChildren(...rows);
}

function evidenceSource(record) {
  if (!record || typeof record !== "object") return "Persisted tool event";
  const source = record.source_system || record.source || null;
  const reference = record.source_reference || null;
  const verifiedAt = record.verified_at || null;
  return [
    source,
    reference,
    verifiedAt ? `verified ${formatTime(verifiedAt)}` : null,
  ].filter(Boolean).join(" · ") || "Persisted tool event";
}

function eventPresentation(event) {
  const input = event.inputs_json && typeof event.inputs_json === "object" ? event.inputs_json : event.inputs || {};
  const output = event.output_json && typeof event.output_json === "object" ? event.output_json : event.output || {};
  switch (event.tool) {
    case "lookup_fault": {
      const fault = output.fault || {};
      return output.matched
        ? {
            title: "Verified network fault matched",
            detail: `${formatLabel(fault.fault_type)} affecting ${fault.area || input.cell_id || "the caller's site"}.`,
            evidence: evidenceSource(fault),
            tone: "success",
          }
        : {
            title: "No active network fault matched",
            detail: `The verified incident register was checked for ${input.cell_id || "the caller's site"}.`,
            evidence: "Exact cell lookup completed",
            tone: "neutral",
          };
    }
    case "inspect_account":
      return output.found
        ? {
            title: "Account state verified",
            detail: `${output.barred ? "Line barred" : "Line active"} · ${output.data_balance_mb ?? "Unknown"} MB balance${output.compensation_eligible ? " · compensation eligible" : ""}.`,
            evidence: evidenceSource(output),
            tone: output.barred ? "attention" : "success",
          }
        : {
            title: "Account state unavailable",
            detail: "No account change was made because an authoritative record was not available.",
            evidence: "Safe fallback applied",
            tone: "attention",
          };
    case "lookup_playbook": {
      const playbook = output.playbook || {};
      return output.matched
        ? {
            title: "Approved guidance selected",
            detail: playbook.title || `Playbook matched for ${formatLabel(input.issue_type)}.`,
            evidence: evidenceSource(playbook),
            tone: "success",
          }
        : {
            title: "No approved playbook matched",
            detail: `The playbook register was checked for ${formatLabel(input.issue_type)}.`,
            evidence: "Generic safe guidance used",
            tone: "neutral",
          };
    }
    case "queue_compensation":
      return {
        title: "Compensation queued",
        detail: `${output.amount_mb || 500} MB data credit entered the delivery queue.`,
        evidence: `Command status: ${formatLabel(output.status || "queued")}`,
        tone: "success",
      };
    case "schedule_callback":
      return {
        title: "Service callback scheduled",
        detail: "A restoration update entered the operator delivery queue.",
        evidence: `Command status: ${formatLabel(output.status || "queued")}`,
        tone: "success",
      };
    case "verify_resolution":
      return {
        title: output.resolved ? "Caller confirmed service restoration" : "Caller reported the issue remains",
        detail: output.resolved ? "The case passed its final service check." : "The unresolved path triggered a specialist handoff.",
        evidence: `Attempted action: ${formatLabel(input.attempted_action)}`,
        tone: output.resolved ? "success" : "attention",
      };
    case "create_handoff":
      return {
        title: "Specialist handoff opened",
        detail: `Ticket ${output.ticket_id || "created"} contains a structured PII-safe summary.`,
        evidence: `Ticket status: ${formatLabel(output.status || "open")}`,
        tone: "attention",
      };
    case "record_complaint_signal":
      return {
        title: "Complaint signal recorded",
        detail: `${output.distinct_callers || 0} distinct callers now report ${formatLabel(input.symptom)} at ${input.cell_id || "this site"}.`,
        evidence: "Duplicate callers count once per incident window",
        tone: "neutral",
      };
    case "propose_candidate_incident":
      return {
        title: "Candidate incident proposed",
        detail: `The ${output.evidence_count || 0}-caller threshold produced an item for NOC review.`,
        evidence: "Status: Unconfirmed — operator verification required",
        tone: "attention",
      };
    default:
      return {
        title: formatLabel(event.tool),
        detail: "A policy-controlled tool event was persisted for this call.",
        evidence: "Auditable event ledger",
        tone: "neutral",
      };
  }
}

function renderEvents(events) {
  elements.eventTimeline.replaceChildren();
  elements.eventCount.textContent = `${events.length} ${events.length === 1 ? "event" : "events"}`;
  if (!events.length) {
    elements.eventTimeline.append(createElement("li", "trace-empty", "This call completed without a tool event."));
    return;
  }
  const items = events.map((event, index) => {
    const presentation = eventPresentation(event);
    const item = createElement("li", `trace-event trace-${presentation.tone}`);
    const marker = createElement("span", "trace-marker", String(index + 1).padStart(2, "0"));
    marker.setAttribute("aria-hidden", "true");
    const body = createElement("div", "trace-body");
    const heading = createElement("div", "trace-heading");
    heading.append(
      createElement("strong", "", presentation.title),
      createElement("time", "", formatTime(event.created_at)),
    );
    body.append(
      heading,
      createElement("p", "", presentation.detail),
      createElement("small", "", presentation.evidence),
    );
    item.append(marker, body);
    return item;
  });
  elements.eventTimeline.append(...items);
}

function showInspector() {
  document.body.classList.add("inspector-open");
  if (typeof elements.inspector.showModal === "function") {
    if (!elements.inspector.open) elements.inspector.showModal();
  } else {
    elements.inspector.setAttribute("open", "");
  }
}

function closeCallInspector() {
  state.inspectorRequest?.abort();
  state.inspectorRequest = null;
  document.body.classList.remove("inspector-open");
  if (typeof elements.inspector.close === "function" && elements.inspector.open) {
    elements.inspector.close();
  } else {
    elements.inspector.removeAttribute("open");
  }
}

async function openCallInspector(call) {
  state.inspectorRequest?.abort();
  const controller = new AbortController();
  state.inspectorRequest = controller;
  elements.inspectorCallId.textContent = `Case ${call.call_id || "reference unavailable"}`;
  elements.inspectorLocation.textContent = `${call.area || "Area unavailable"} · ${call.cell_id || "Cell unavailable"}`;
  elements.inspectorLanguage.textContent = call.language_pair || "Unavailable";
  elements.inspectorIssue.textContent = formatLabel(call.symptom);
  elements.inspectorOutcome.textContent = formatLabel(call.outcome);
  elements.inspectorTranscript.textContent = call.safe_transcript || "No transcript is available for this call.";
  elements.inspectorResponse.textContent = call.response || "No response was recorded.";
  elements.inspectorError.textContent = "";
  elements.eventTimeline.replaceChildren();
  elements.eventCount.textContent = "Loading";
  elements.inspectorLoading.hidden = false;
  elements.inspectorContent.hidden = true;
  showInspector();
  try {
    const response = await fetch(`/internal/calls/${encodeURIComponent(call.call_id)}/events`, {
      headers: { "X-Internal-API-Key": state.key },
      cache: "no-store",
      signal: controller.signal,
    });
    let events = null;
    try {
      events = await response.json();
    } catch {
      // A clear status-specific error is shown below for an unreadable response.
    }
    if (!response.ok) {
      throw new Error(response.status === 401 ? "Your operations session has expired." : "The decision trace is unavailable.");
    }
    if (!Array.isArray(events)) throw new Error("The decision trace could not be read.");
    renderEvents(events);
  } catch (error) {
    if (error.name === "AbortError") return;
    renderEvents([]);
    elements.inspectorError.textContent = error.message;
  } finally {
    if (state.inspectorRequest === controller) {
      state.inspectorRequest = null;
      elements.inspectorLoading.hidden = true;
      elements.inspectorContent.hidden = false;
    }
  }
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
elements.closeInspector.addEventListener("click", closeCallInspector);
elements.inspector.addEventListener("click", (event) => {
  if (event.target === elements.inspector) closeCallInspector();
});
elements.inspector.addEventListener("close", () => {
  state.inspectorRequest?.abort();
  state.inspectorRequest = null;
  document.body.classList.remove("inspector-open");
});
checkHealth();
if (state.key) {
  loadDashboard().catch(() => {
    sessionStorage.removeItem("faultbridgeInternalKey");
    elements.apiKey.value = "";
  });
}
