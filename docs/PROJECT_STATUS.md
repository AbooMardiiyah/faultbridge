# Project Status

Updated 12 September 2026. This file records durable working context for future
sessions; the Git history remains the authoritative implementation record.

## Completed

- Provider-neutral voice pipeline with Sahara streaming STT and TTS adapters.
- PostgreSQL persistence, migrations, verified incident/account/playbook inputs,
  PII redaction, pseudonymous callers, retention, and deletion.
- Three-tier orchestration: known-fault handling, guided diagnosis with outcome
  verification, and escalation with crowd-signal candidate incidents.
- Durable compensation and callback queues, workers, and operator webhooks.
- Industry-oriented ASR, robustness, privacy, routing, and agent evaluation tools.
- Responsive caller and operations interfaces using real protected API endpoints.
- Operations call inspector for redacted transcripts, grounded answers, and
  operator-readable timelines built from persisted tool events.
- Docker Compose packaging for the API and PostgreSQL, with Make targets and
  health checks; both web surfaces and the protected-data boundary are smoke-tested.
- Frozen AfriSwitch panel with 400 hash-verified clips (100 per language pair) and
  a 1,600-row deterministic telephone/noise/loss robustness manifest.
- Frozen 100-prompt code-switched TTS panel and an executable Sahara generation,
  independent-ASR fidelity, latency, waveform, and consensus scoring pipeline.
- Live Sahara pilots passed for female Hausa, Igbo, Pidgin, and Yoruba voices and
  one male Hausa voice. All five outputs were valid, hash-verified WAV files with
  no clipping; the four female prompts averaged 9.18 seconds to first audio. These
  are contract diagnostics, not final benchmark results.
- One natural Hausa-English Sahara STT pilot succeeded after a transient provider
  failure: normalized WER 28.6%, CER 7.4%, and 5.31 seconds of post-audio latency.
  The sample size is one and must not appear as a model-level conclusion.

## Current access

- AfriSwitch access is approved and `HF_TOKEN` is configured locally. The frozen
  400-clip benchmark panel and 1,600-condition robustness panel are prepared.
- AssemblyAI credentials are optional for a fifth commercial sensitivity run. The
  four-model core panel does not depend on them.
- `SAHARA_VOICEBOT_WORKFLOW_ID` is needed only if the demo uses an outbound Sahara
  Conversation Call; the browser microphone flow does not require it.
- The submission portal access code and final YouTube upload remain user-owned.

Intron will require explicit language selection on every ASR and TTS request from
14 September at 08:00 WAT. The Sahara adapters and browser caller now send the
documented STT and TTS language codes explicitly. New mission prizes recognize two
benchmark datasets and one benchmark report, alongside the Fintech, Telco & Call
Center category prize, so benchmark rigor remains the highest-priority workstream.

The live TTS server returned complete `READY` audio but omitted the documented
`COMMITTED_AUDIO` summary. The adapter now sends `COMMIT`, waits 10 seconds for the
summary, and preserves the already validated WAV when only the summary times out.
The original failed pilot and five successful contract pilots remain in the
ignored `eval/results/tts/pilots/` audit directory.

## Active sequence

1. Run one-clip ASR performance pilots, then complete the frozen provider panel
   with resumable raw results.
2. Generate and independently transcribe the female/male Sahara TTS panel; conduct
   the predeclared bilingual-listener audit.
3. Test the caller and operations interfaces against live providers.
4. Score ASR, TTS, and agent results, generate the report, and derive
   evidence-based routing recommendations.
5. Complete the telco scenarios, privacy set, five-minute demo, and submission
   package.

Hardware use and foreground validation are now authorized. Keep delivery workers
disabled until real operator webhooks are configured.

After benchmark and live-call validation, add OpenTelemetry traces and metrics for
the voice turn stages, database tools, and provider calls. An optional Cekura run
can provide independent black-box conversation evidence if access is available;
it complements the frozen AfriSwitch, privacy, and executable-state scorecards.
