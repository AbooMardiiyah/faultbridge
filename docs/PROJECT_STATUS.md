# Project Status

Updated 13 September 2026. This file records durable working context for future
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
- Complete four-model ASR comparison on all 400 frozen clips. The committed report
  and machine-readable aggregate cover Sahara, SBPN, Faster-Whisper Turbo, and
  Meta OmniASR with 24 paired comparisons and 96 diagnostic slices. A private raw
  evidence bundle reproduces the committed aggregate byte-for-byte.
- Live Sahara pilots passed for female Hausa, Igbo, Pidgin, and Yoruba voices and
  one male Hausa voice. All five outputs were valid, hash-verified WAV files with
  no clipping; the four female prompts averaged 9.18 seconds to first audio. These
  are contract diagnostics, not final benchmark results.
- The official Sahara TTS panel is complete: all 200 female/male outputs succeeded
  on their first paid request. All WAV hashes verify; the files are 22.05 kHz mono
  PCM16, total 1,672.29 audio seconds and 71 MB, with no clipped samples. At the
  posted NGN 0.65 per generated second, measured generation cost is approximately
  NGN 1,086.99.
- Faster-Whisper Turbo, SBPN, and OmniASR each judged all 200 TTS outputs with no
  missing or empty results. The public 24-cell aggregate and automatic report
  cover organizer-requested WER, hallucination, transcript loss, segment loss,
  and strict accuracy. A deterministic 40-output bilingual audit is prepared;
  human ratings remain pending and no MOS is claimed.
- The reproducible PII scorecard covers 100 synthetic code-switched telco cases,
  balanced across four language pairs, with 100 typed phone, email, account/SIM,
  and numeric-identifier spans. It achieved 100% exact typed-span precision,
  recall, and F1 with zero hard leakages within this declared rule-based scope.
- A 48-scenario executable agent panel is frozen and balanced across all four
  language pairs and 12 resolution/safety capabilities. Its expected tool traces
  and database effects pass against the real isolated PostgreSQL policy stack.
  Together-hosted Llama 3.3 70B is configured and has passed a live pilot; the
  full external-model run remains.
- The named-ASR downstream panel has 24 distinct synthetic telco utterances, six
  per language. Sahara TTS generated all 24 successfully (161.14 audio seconds),
  and Sahara, Faster-Whisper, OmniASR, and SBPN transcribed every file. The final
  360-run Together panel achieved 100.0% strict task success for Sahara, 95.8%
  for SBPN, 87.5% for OmniASR, and 79.2% for Faster-Whisper, with 0% critical
  failure for every provider. Raw evidence remains reproducible from hashes.
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
- The private four-model ASR evidence is uploaded to
  `Tiamz/faultbridge-asr-benchmark-evidence` at revision
  `ef320d7f367e040c47b4021a397011dae894fe00`.
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

The exploratory WebSocket log retains 46 attempts across 45 prompt/voice cells:
9 valid WAVs and 36 final failures. Thirty-five failures were reserved-bit protocol
closures and one was a provider chunk-size rejection. These are retained as
transport diagnostics and are not mixed into the official TTS panel.

TTS generator v6 uses the documented synchronous generate endpoint in a separate
append-only log. It submits each prompt once, polls the returned text ID after a
documented HTTP 503 timeout, records rate-limit headers, and downloads audio
without forwarding the bearer token to object storage. Requests are sequential
and spaced 2.1 seconds apart for the documented 30-request-per-minute limit.

## Active sequence

1. Run and score the full 48-scenario Together panel, then derive evidence-based
   routing recommendations from both agent scorecards.
2. Conduct the prepared TTS audit with three bilingual listeners per language
   pair and add only qualified human results to the report.
3. Deploy to Railway and test the caller and operations interfaces against live
   providers.
4. Produce the three-page PDF, five-minute video, public repository release,
   Responsible AI note, and optional Hugging Face audio submission.
5. Walk through `docs/FAULTBRIDGE_TECHNICAL_GUIDE.md` and rehearse the technical
   defense and likely judge questions with the project owner.

Hardware use and foreground validation are now authorized. Keep delivery workers
disabled until real operator webhooks are configured.

After benchmark and live-call validation, add OpenTelemetry traces and metrics for
the voice turn stages, database tools, and provider calls. An optional Cekura run
can provide independent black-box conversation evidence if access is available;
it complements the frozen AfriSwitch, privacy, and executable-state scorecards.
