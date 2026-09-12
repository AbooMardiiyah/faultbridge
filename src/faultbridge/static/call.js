const elements = {
  form: document.querySelector("#call-form"),
  languagePair: document.querySelector("#language-pair"),
  area: document.querySelector("#area"),
  cellId: document.querySelector("#cell-id"),
  callerId: document.querySelector("#caller-id"),
  consent: document.querySelector("#consent"),
  internalKey: document.querySelector("#internal-key"),
  demoAccess: document.querySelector(".demo-access"),
  recordButton: document.querySelector("#record-button"),
  recordLabel: document.querySelector("#record-label"),
  recordHelp: document.querySelector("#record-help"),
  resetButton: document.querySelector("#reset-call"),
  error: document.querySelector("#call-error"),
  conversation: document.querySelector("#conversation"),
  welcome: document.querySelector("#welcome"),
  statusTitle: document.querySelector("#status-title"),
  statusCopy: document.querySelector("#status-copy"),
  voiceVisual: document.querySelector("#voice-visual"),
  statePill: document.querySelector("#call-state"),
  decisionPanel: document.querySelector("#decision-panel"),
  outcomeLabel: document.querySelector("#outcome-label"),
  agentSteps: document.querySelector("#agent-steps"),
  playResponse: document.querySelector("#play-response"),
  healthDot: document.querySelector("#health-dot"),
  healthLabel: document.querySelector("#health-label"),
};

const state = {
  key: sessionStorage.getItem("faultbridgeInternalKey") || "",
  recording: false,
  processing: false,
  audioContext: null,
  mediaStream: null,
  sourceNode: null,
  recorderNode: null,
  silentNode: null,
  samples: [],
  sampleRate: 0,
  stopTimer: null,
  callId: null,
  phase: "start",
  responseAudio: [],
  playingAudio: null,
  playingUrl: null,
  playbackId: 0,
};

const voiceProfiles = {
  "Pidgin-English": { language: "pcm", accent: "pidgin" },
  "Hausa-English": { language: "ha", accent: "hausa" },
  "Igbo-English": { language: "ig", accent: "igbo" },
  "Yoruba-English": { language: "yo", accent: "yoruba" },
};

const outcomes = {
  awaiting_verification: "Guidance ready to test",
  known_fault_handled: "Known fault confirmed",
  guided_fix_resolved: "Service restored",
  escalated: "Specialist handoff created",
  consent_declined: "Voice processing stopped",
};

const toolDescriptions = {
  lookup_fault: ["Checked network status", "Compared this site with verified active incidents."],
  inspect_account: ["Checked account state", "Reviewed the latest available account evidence."],
  lookup_playbook: ["Selected verified guidance", "Used an approved troubleshooting playbook."],
  apply_compensation: ["Queued data credit", "Created an auditable compensation request."],
  queue_compensation: ["Queued data credit", "Created an auditable compensation request."],
  schedule_callback: ["Scheduled service update", "Queued a callback for the verified incident."],
  verify_resolution: ["Verified caller outcome", "Used your service test to decide the next action."],
  create_handoff: ["Opened specialist handoff", "Prepared a PII-safe summary for an operator."],
  record_complaint_signal: ["Added network evidence", "Counted this unresolved report once for the site."],
  propose_candidate_incident: ["Proposed NOC review", "Flagged a repeated complaint pattern for verification."],
};

function setCallState(mode, label) {
  elements.statePill.className = `state-pill ${mode}`.trim();
  elements.statePill.lastChild.textContent = ` ${label}`;
}

function setFormDisabled(disabled) {
  for (const control of elements.form.elements) control.disabled = disabled;
}

function setError(message = "") {
  elements.error.textContent = message;
}

function showWelcome(title, copy) {
  elements.welcome.hidden = false;
  elements.statusTitle.textContent = title;
  elements.statusCopy.textContent = copy;
}

function scrollConversation() {
  elements.conversation.scrollTo({
    top: elements.conversation.scrollHeight,
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
  });
}

function addMessage(role, messageText, redacted = false) {
  const message = document.createElement("article");
  message.className = `message ${role}`;
  const label = document.createElement("p");
  label.className = "message-label";
  label.textContent = role === "caller" ? "You" : "FaultBridge";
  const bubble = document.createElement("p");
  bubble.className = "message-bubble";
  bubble.textContent = messageText;
  message.append(label, bubble);
  if (redacted) {
    const note = document.createElement("span");
    note.className = "privacy-note";
    note.textContent = "✓ Personal details masked";
    message.append(note);
  }
  elements.conversation.append(message);
  scrollConversation();
}

function formatLabel(value) {
  return String(value || "Complete")
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}

function renderDecision(call) {
  const outcome = call?.outcome || "awaiting_verification";
  elements.outcomeLabel.textContent = outcomes[outcome] || formatLabel(outcome);
  elements.agentSteps.replaceChildren();
  const events = Array.isArray(call?.events) ? call.events : [];
  for (const event of events) {
    const description = toolDescriptions[event.tool];
    if (!description) continue;
    const item = document.createElement("li");
    const title = document.createElement("b");
    const detail = document.createElement("span");
    title.textContent = description[0];
    detail.textContent = description[1];
    item.append(title, detail);
    elements.agentSteps.append(item);
  }
  if (!elements.agentSteps.childElementCount) {
    const item = document.createElement("li");
    const title = document.createElement("b");
    const detail = document.createElement("span");
    title.textContent = "Response prepared";
    detail.textContent = "The call was processed under the active safety policy.";
    item.append(title, detail);
    elements.agentSteps.append(item);
  }
  elements.decisionPanel.hidden = false;
}

function responseError(response, payload) {
  if (response.status === 401) return "The internal access key is not valid.";
  if (response.status === 413) return "That recording is too long. Try a shorter message.";
  if (response.status === 503) return payload?.detail || "The voice service is not configured yet.";
  return payload?.detail || "We could not process that message. Please try again.";
}

function base64Audio(value) {
  const binary = window.atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return new Blob([bytes], { type: "audio/wav" });
}

async function playResponseAudio() {
  if (!state.responseAudio.length || state.playingAudio) return;
  const playbackId = ++state.playbackId;
  elements.playResponse.disabled = true;
  elements.playResponse.lastChild.textContent = " Playing";
  try {
    for (const encodedChunk of state.responseAudio) {
      if (playbackId !== state.playbackId) break;
      const url = URL.createObjectURL(base64Audio(encodedChunk));
      const audio = new Audio(url);
      state.playingAudio = audio;
      state.playingUrl = url;
      try {
        const finished = new Promise((resolve, reject) => {
          audio.addEventListener("ended", resolve, { once: true });
          audio.addEventListener("error", reject, { once: true });
        });
        await audio.play();
        await finished;
      } finally {
        URL.revokeObjectURL(url);
        state.playingAudio = null;
        state.playingUrl = null;
      }
    }
  } catch {
    if (playbackId === state.playbackId) {
      setError("The voice response could not be played. The written response is still available above.");
    }
  } finally {
    elements.playResponse.disabled = false;
    elements.playResponse.lastChild.textContent = " Play response";
  }
}

function mergeSamples(sampleChunks) {
  const length = sampleChunks.reduce((total, chunk) => total + chunk.length, 0);
  const samples = new Float32Array(length);
  let offset = 0;
  for (const chunk of sampleChunks) {
    samples.set(chunk, offset);
    offset += chunk.length;
  }
  return samples;
}

function resample(samples, sourceRate, targetRate = 16000) {
  if (sourceRate === targetRate) return samples;
  const outputLength = Math.max(1, Math.round(samples.length * targetRate / sourceRate));
  const output = new Float32Array(outputLength);
  const ratio = sourceRate / targetRate;
  for (let index = 0; index < outputLength; index += 1) {
    if (ratio > 1) {
      const start = Math.floor(index * ratio);
      const end = Math.min(Math.floor((index + 1) * ratio), samples.length);
      let total = 0;
      for (let sourceIndex = start; sourceIndex < end; sourceIndex += 1) total += samples[sourceIndex];
      output[index] = total / Math.max(1, end - start);
      continue;
    }
    const position = index * ratio;
    const left = Math.floor(position);
    const right = Math.min(left + 1, samples.length - 1);
    const weight = position - left;
    output[index] = samples[left] * (1 - weight) + samples[right] * weight;
  }
  return output;
}

function pcm16(samples) {
  const buffer = new ArrayBuffer(samples.length * 2);
  const view = new DataView(buffer);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    const value = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    view.setInt16(index * 2, Math.round(value), true);
  }
  return buffer;
}

async function startRecorder() {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("Voice recording is not supported by this browser.");
  state.mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) throw new Error("Voice recording is not supported by this browser.");
  state.audioContext = new AudioContextClass();
  await state.audioContext.resume();
  state.sampleRate = state.audioContext.sampleRate;
  state.samples = [];
  state.sourceNode = state.audioContext.createMediaStreamSource(state.mediaStream);
  state.silentNode = state.audioContext.createGain();
  state.silentNode.gain.value = 0;
  state.silentNode.connect(state.audioContext.destination);
  if (state.audioContext.audioWorklet && window.AudioWorkletNode) {
    try {
      await state.audioContext.audioWorklet.addModule("/assets/recorder-worklet.js");
      state.recorderNode = new window.AudioWorkletNode(state.audioContext, "faultbridge-recorder");
      state.recorderNode.port.onmessage = (event) => state.samples.push(event.data);
    } catch {
      state.recorderNode = null;
    }
  }
  if (!state.recorderNode) {
    if (!state.audioContext.createScriptProcessor) throw new Error("This browser cannot capture PCM audio.");
    state.recorderNode = state.audioContext.createScriptProcessor(4096, 1, 1);
    state.recorderNode.onaudioprocess = (event) => {
      state.samples.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };
  }
  state.sourceNode.connect(state.recorderNode);
  state.recorderNode.connect(state.silentNode);
}

async function releaseRecorder() {
  window.clearTimeout(state.stopTimer);
  state.stopTimer = null;
  state.mediaStream?.getTracks().forEach((track) => track.stop());
  state.sourceNode?.disconnect();
  state.recorderNode?.disconnect();
  state.silentNode?.disconnect();
  if (state.recorderNode?.port) state.recorderNode.port.onmessage = null;
  if (state.recorderNode && "onaudioprocess" in state.recorderNode) state.recorderNode.onaudioprocess = null;
  if (state.audioContext && state.audioContext.state !== "closed") await state.audioContext.close();
  state.mediaStream = null;
  state.audioContext = null;
  state.sourceNode = null;
  state.recorderNode = null;
  state.silentNode = null;
}

async function beginRecording() {
  if (state.processing) return;
  setError();
  if (!elements.internalKey.value.trim()) elements.demoAccess.open = true;
  if (!elements.form.reportValidity()) {
    return;
  }
  state.processing = true;
  elements.recordButton.disabled = true;
  elements.recordLabel.textContent = "Requesting microphone…";
  elements.resetButton.disabled = true;
  cancelPlayback();
  state.key = elements.internalKey.value.trim();
  sessionStorage.setItem("faultbridgeInternalKey", state.key);
  try {
    await startRecorder();
  } catch (error) {
    await releaseRecorder();
    state.processing = false;
    elements.recordButton.disabled = false;
    elements.recordLabel.textContent = state.phase === "verify" ? "Record result" : "Start speaking";
    elements.resetButton.disabled = false;
    const denied = error?.name === "NotAllowedError";
    setError(denied ? "Microphone access was declined. Allow access in your browser to continue." : error.message);
    return;
  }
  state.processing = false;
  state.recording = true;
  elements.recordButton.disabled = false;
  elements.recordButton.setAttribute("aria-pressed", "true");
  setFormDisabled(true);
  elements.recordButton.classList.add("recording");
  elements.recordLabel.textContent = "Stop recording";
  elements.recordHelp.textContent = "Listening now. Press stop when you finish speaking.";
  elements.voiceVisual.classList.add("active");
  showWelcome("Listening…", state.phase === "verify" ? "Tell us whether the service works now." : "Describe the problem in your preferred language.");
  setCallState("recording", "Listening");
  state.stopTimer = window.setTimeout(() => stopRecording(), 90000);
}

function requestUrl() {
  const profile = voiceProfiles[elements.languagePair.value] || voiceProfiles["Pidgin-English"];
  const params = new URLSearchParams({
    language_pair: elements.languagePair.value,
    voice_language: profile.language,
    voice_accent: profile.accent,
  });
  if (state.phase === "verify") return `/internal/voice/calls/${encodeURIComponent(state.callId)}/verify?${params}`;
  params.set("caller_id", elements.callerId.value.trim());
  params.set("area", elements.area.value.trim());
  params.set("cell_id", elements.cellId.value.trim());
  params.set("consent", String(elements.consent.checked));
  return `/internal/voice/calls?${params}`;
}

async function submitAudio(audio) {
  const response = await fetch(requestUrl(), {
    method: "POST",
    headers: { "Content-Type": "audio/L16", "X-Internal-API-Key": state.key },
    body: audio,
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // The status-specific fallback below remains useful for non-JSON failures.
  }
  if (!response.ok) throw new Error(responseError(response, payload));
  return payload;
}

async function stopRecording() {
  if (!state.recording) return;
  state.recording = false;
  elements.recordButton.setAttribute("aria-pressed", "false");
  state.processing = true;
  elements.recordButton.classList.remove("recording");
  elements.recordButton.disabled = true;
  elements.recordLabel.textContent = "Checking service…";
  elements.recordHelp.textContent = "FaultBridge is transcribing and checking verified records.";
  elements.voiceVisual.classList.remove("active");
  showWelcome("Checking the evidence…", "This may take a few seconds.");
  setCallState("processing", "Processing");
  await releaseRecorder();
  const captured = mergeSamples(state.samples);
  if (captured.length < state.sampleRate * 0.35) {
    state.processing = false;
    if (state.phase === "start") setFormDisabled(false);
    elements.recordButton.disabled = false;
    elements.resetButton.disabled = false;
    elements.recordLabel.textContent = state.phase === "verify" ? "Record result" : "Start speaking";
    elements.recordHelp.textContent = "We did not hear enough audio. Try speaking for a little longer.";
    setCallState("", "Ready");
    return;
  }
  try {
    const audio = pcm16(resample(captured, state.sampleRate));
    const payload = await submitAudio(audio);
    elements.welcome.hidden = true;
    addMessage("caller", payload.transcript, /redacted/i.test(payload.transcript));
    addMessage("agent", payload.response_text);
    renderDecision(payload.call);
    state.callId = payload.call?.call_id || state.callId;
    state.responseAudio = Array.isArray(payload.response_audio_chunks_base64) ? payload.response_audio_chunks_base64 : [];
    elements.playResponse.hidden = state.responseAudio.length === 0;
    const awaitingVerification = payload.call?.outcome === "awaiting_verification";
    state.phase = awaitingVerification ? "verify" : "complete";
    elements.recordButton.disabled = !awaitingVerification;
    elements.recordLabel.textContent = awaitingVerification ? "Record result" : "Call complete";
    elements.recordHelp.textContent = awaitingVerification
      ? "Try the suggested step, then tell us whether it worked."
      : "Your microphone is off. Use Start over for another issue.";
    elements.resetButton.hidden = false;
    elements.resetButton.disabled = false;
    setCallState("", awaitingVerification ? "Awaiting test" : "Complete");
  } catch (error) {
    setError(error.message);
    elements.recordButton.disabled = false;
    elements.resetButton.disabled = false;
    elements.recordLabel.textContent = state.phase === "verify" ? "Record result" : "Try again";
    elements.recordHelp.textContent = "Your microphone is off. You can safely try again.";
    setCallState("", "Ready");
  } finally {
    state.processing = false;
    if (state.phase === "start") setFormDisabled(false);
  }
}

function cancelPlayback() {
  state.playbackId += 1;
  if (state.playingAudio) {
    state.playingAudio.pause();
    state.playingAudio.dispatchEvent(new Event("ended"));
    state.playingAudio = null;
  }
  if (state.playingUrl) {
    URL.revokeObjectURL(state.playingUrl);
    state.playingUrl = null;
  }
  elements.playResponse.disabled = false;
  elements.playResponse.lastChild.textContent = " Play response";
}

function resetCall() {
  cancelPlayback();
  state.callId = null;
  state.phase = "start";
  state.responseAudio = [];
  setError();
  elements.conversation.querySelectorAll(".message").forEach((message) => message.remove());
  showWelcome("Ready when you are", "Press the microphone and describe what is happening with your service.");
  elements.decisionPanel.hidden = true;
  elements.agentSteps.replaceChildren();
  elements.playResponse.hidden = true;
  elements.resetButton.hidden = true;
  elements.recordButton.disabled = false;
  elements.recordButton.setAttribute("aria-pressed", "false");
  elements.recordLabel.textContent = "Start speaking";
  elements.recordHelp.textContent = "Your microphone turns off when you press stop.";
  setFormDisabled(false);
  setCallState("", "Ready");
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

elements.internalKey.value = state.key;
if (!state.key) elements.demoAccess.open = true;
elements.recordButton.addEventListener("click", () => {
  if (state.recording) {
    stopRecording();
  } else {
    beginRecording();
  }
});
elements.resetButton.addEventListener("click", resetCall);
elements.playResponse.addEventListener("click", playResponseAudio);
window.addEventListener("pagehide", () => {
  if (state.mediaStream || state.audioContext) releaseRecorder();
});
checkHealth();
