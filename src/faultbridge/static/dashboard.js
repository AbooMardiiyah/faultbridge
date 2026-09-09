const state = { key: sessionStorage.getItem("faultbridgeInternalKey") || "" };

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
})[character]);

const formatTime = (value) => value ? new Intl.DateTimeFormat(undefined, {
  hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short"
}).format(new Date(value)) : "—";

async function loadDashboard() {
  const response = await fetch("/internal/dashboard", {
    headers: { "X-Internal-API-Key": state.key }
  });
  if (!response.ok) throw new Error(response.status === 401 ? "Invalid internal API key" : "Dashboard unavailable");
  const data = await response.json();
  document.querySelector("#access-panel").hidden = true;
  document.querySelector("#workspace").hidden = false;
  document.querySelector("#call-count").textContent = data.calls.length;
  document.querySelector("#ticket-count").textContent = data.tickets.filter((item) => item.status === "open").length;
  document.querySelector("#candidate-count").textContent = data.candidate_incidents.length;
  const actions = [...data.compensation_commands, ...data.callback_commands];
  document.querySelector("#action-count").textContent = actions.filter((item) => item.status === "queued").length;

  document.querySelector("#calls").innerHTML = data.calls.length ? data.calls.map((call) => `
    <tr><td>${formatTime(call.created_at)}</td><td><strong>${escapeHtml(call.area)}</strong><br>${escapeHtml(call.cell_id)}</td>
    <td>${escapeHtml(call.language_pair)}</td><td>${escapeHtml(call.symptom)}</td>
    <td><span class="pill">${escapeHtml(call.outcome)}</span></td></tr>`).join("") : '<tr><td colspan="5" class="empty">No calls recorded</td></tr>';

  document.querySelector("#candidates").innerHTML = data.candidate_incidents.length ? data.candidate_incidents.map((item) => `
    <div class="card"><div><strong>${escapeHtml(item.cell_id)} · ${escapeHtml(item.symptom)}</strong>
    <small>${escapeHtml(item.status)} · ${item.evidence_count} distinct callers</small></div><span>${formatTime(item.updated_at)}</span></div>`).join("") : '<p class="empty">No candidate incidents</p>';

  document.querySelector("#actions").innerHTML = actions.length ? actions.map((item) => `
    <div class="card"><div><strong>${item.amount_mb ? `${item.amount_mb} MB compensation` : escapeHtml(item.trigger)}</strong>
    <small>${escapeHtml(item.status)} · attempt ${item.attempt_count}</small></div><span>${formatTime(item.updated_at)}</span></div>`).join("") : '<p class="empty">No actions queued</p>';
}

async function checkHealth() {
  try {
    const response = await fetch("/health/ready");
    if (!response.ok) throw new Error();
    document.querySelector("#health-dot").classList.add("ready");
    document.querySelector("#health-label").textContent = "Systems ready";
  } catch {
    document.querySelector("#health-label").textContent = "System unavailable";
  }
}

document.querySelector("#access-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  state.key = document.querySelector("#api-key").value;
  try {
    await loadDashboard();
    sessionStorage.setItem("faultbridgeInternalKey", state.key);
  } catch (error) {
    document.querySelector("#access-error").textContent = error.message;
  }
});

document.querySelector("#refresh").addEventListener("click", loadDashboard);
checkHealth();
if (state.key) loadDashboard().catch(() => sessionStorage.removeItem("faultbridgeInternalKey"));
