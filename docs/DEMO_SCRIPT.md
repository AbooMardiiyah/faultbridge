# FaultBridge Five-Minute Demo Guide

Record at 1440p or 1080p. Keep the browser at 100% zoom, close notifications,
and use only synthetic caller details. Open the caller page at `/` and the
operations workspace at `/operations` in separate tabs before recording. Enter
the internal access key off camera.

## Recording Checklist

- Confirm the API and PostgreSQL health with `make docker-status`.
- Confirm Sahara and Together credentials are configured without displaying them.
- Use a headset or the prepared synthetic audio file to avoid room noise.
- Keep `docs/BENCHMARK_REPORT.pdf` open at page 1.
- Record one uninterrupted product flow, then add narration and title cards.
- Keep the final video under 4 minutes 50 seconds to allow for upload processing.

## Script and Screen Actions

### 0:00 to 0:25 | The problem

**Show:** FaultBridge caller page.

**Say:** “Nigerian telco customers often describe faults by switching between a
local language and English. Support systems can misunderstand the complaint or
give an answer that is not grounded in network data. FaultBridge listens,
protects personal data, checks verified telco state, and turns repeated unresolved
calls into evidence for network operations.”

### 0:25 to 1:45 | Resolve a known fault

**Show:** Select `Hausa-English`, area `Evaluation Area 02`, cell `EVAL-002`, and
synthetic callback number `08030000002`. Check consent and start the call.

**Play or say:** “Network dina ya daina aiki, babu signal kwata-kwata. I consent
to automated processing.”

Prepared audio: `benchmark/agent_audio/female/downstream-agent-002-known-fault-eligible-female-r1.wav`.

**Show:** The grounded response and completed actions.

**Say:** “Sahara transcribes the code-switched speech with an explicit Hausa
language value. FaultBridge redacts sensitive text before analysis. The agent
looks up this exact cell, finds a verified fibre-cut incident, checks the account,
and queues only the compensation and callback allowed by policy. It does not
invent a cause or repair time.”

### 1:45 to 2:40 | Prove the agent used tools

**Show:** Open the operations workspace, unlock it, select the new call, and show
the decision timeline.

**Say:** “The operations view stores a pseudonymous caller reference and the safe
transcript. This trace shows the actual tool sequence: fault lookup, account
inspection, compensation, and callback. Each action is persisted in PostgreSQL
and protected against duplicate delivery.”

Briefly point to candidate incidents and explain: “When no known fault explains a
complaint, three distinct unresolved callers at one cell create an unconfirmed
candidate incident for operator review. FaultBridge never labels crowd evidence
as a confirmed outage.”

### 2:40 to 4:10 | Benchmark evidence

**Show:** Pages 1 and 2 of `docs/BENCHMARK_REPORT.pdf`.

**Say:** “We benchmarked the system at component and task level. The natural ASR
panel contains 400 AfriSwitch clips, 100 for each of Hausa-English, Igbo-English,
Pidgin-English, and Yoruba-English. Every model received the same hash-verified
audio, and failed or empty transcripts stayed in the denominator. Sahara achieved
the lowest equal-language WER at 55.0 percent, ahead of SBPN, OmniASR, and
Faster-Whisper Turbo.”

“For TTS, Sahara generated female and male speech for 100 code-switched prompts.
All 200 outputs succeeded. Three independent ASR families scored transcript
fidelity, while the report clearly separates automatic flags from the pending
human listening audit.”

“We also ran 648 real Llama and PostgreSQL agent executions. On the named-ASR
panel, Sahara transcripts produced 100 percent strict task success, SBPN 95.8,
OmniASR 87.5, and Faster-Whisper 79.2 percent. Every provider had zero critical
safety failures. This measures whether speech errors change the final tool action,
not only whether individual words are wrong.”

### 4:10 to 4:40 | Privacy and reproducibility

**Show:** Page 3 of the report and the repository README.

**Say:** “The privacy scorecard covers 100 labelled synthetic cases and achieved
100 percent exact typed-span precision, recall, and F1 within its declared scope.
Raw benchmark evidence is hash-pinned, aggregates are reproducible from saved
JSON results, and the natural-audio evidence is stored privately on Hugging Face
until its access terms permit publication.”

### 4:40 to 4:55 | Close

**Show:** Caller and operations pages side by side.

**Say:** “FaultBridge gives callers a useful, grounded answer and gives network
teams structured evidence they can act on. It is a production-oriented,
code-switched voice agent built for African telecom support.”

## Recording Fallback

If a live provider is temporarily unavailable, keep the successful local call and
tool trace already captured, state the recording time on screen, and show the raw
result hash. Do not substitute a mocked response or hide a failed request. Record
the benchmark section independently so a provider retry does not require redoing
the entire video.
