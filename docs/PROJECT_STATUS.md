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
- One unscored Faster-Whisper `large-v3` diagnostic completed in 36.58 seconds on
  the 8 GiB machine before the final global baseline changed to OpenAI
  `large-v3-turbo` (809M parameters, four decoder layers). Every reportable sample
  must use the Turbo identifier, and the report must disclose the amendment.
- Two natural Hausa-English Faster-Whisper Turbo CPU pilots completed in 14.70 and
  25.09 seconds. Their combined normalized WER was 96.0%, CER 53.3%, and
  switch-context recall 0%; the second output largely translated or paraphrased
  the input into English. The two-sample pilot is diagnostic evidence only.
- SBPN's published NeMo checkpoint requests the optional `graph_rnnt` training
  loss. The adapter restores it with NeMo's built-in PyTorch RNNT loss because
  loss computation is disabled for transcription. The override leaves the model
  weights and decoding configuration unchanged and is recorded in each result.
- A one-clip SBPN CPU pilot restored the 460 MB checkpoint and transcribed in
  1.05 seconds after model loading. It scored 28.6% normalized WER (6
  substitutions and 4 deletions over 35 reference words), 12.1% CER, and 100%
  switch-context recall. The one-sample result is a contract diagnostic, not a
  model-level accuracy conclusion.
- Meta `omniASR_CTC_300M_v2` passed a one-clip CPU pilot after installing its
  matching fairseq2 and PyTorch 2.8 CPU packages. It transcribed 15.30 seconds of
  audio in 6.34 seconds and scored 34.3% WER and 8.7% CER. Its 1.21 GB checkpoint
  is cached locally; these one-sample figures are diagnostic only.
- The complete 400-clip SBPN run and scorer finished. Its 35 empty outputs
  persisted after one retry and remain in the denominator as failures. Normalized
  WER is 45.1% Hausa, 65.7% Igbo, 39.3% Pidgin, and 82.1% Yoruba. The committed
  single-model report includes clustered confidence intervals and limitations;
  cross-model conclusions wait for the paired provider panel.

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

TTS generator v4 separates time to first audio, time to last audio, and session
close time. Its real-time factor ends at the last audio chunk, so the optional
commit-acknowledgement timeout cannot inflate synthesis latency.

Sahara generation is paused because the account has about $1 of credit. A stopped
run left 38 auditable female-voice outcomes: 4 successes, 32 WebSocket protocol
closures, and 2 provider chunk-size failures. No result was deleted. Credit-safe
Make targets now cap each invocation, resume unattempted samples, distribute
retries fairly, and stop automatically after three consecutive provider failures.

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
