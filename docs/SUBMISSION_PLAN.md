# Intron Submission Package

## What We Will Submit

1. **Problem and solution description.** A short portal response explaining the
   telco fault-information gap, the four code-switched language pairs, and the
   three-tier resolution and discovery flow.
2. **Working application URL.** The public Railway URL for the caller experience
   and operations console. This is supporting evidence even if the form labels it
   optional.
3. **Demo video.** A public or unlisted YouTube link, no longer than five minutes,
   showing real code-switching and a working prototype. Test the link while signed
   out and in an incognito window.
4. **Open-source code and documentation.** The public GitHub repository at the
   exact submitted commit, with setup, architecture, privacy, benchmark, and
   deployment instructions.
5. **Benchmark report.** A maximum three-page PDF comparing Sahara, SBPN,
   Faster-Whisper, and OmniASR. It must cover data, preprocessing, metric
   definitions, per-language ASR results, TTS results, downstream task performance,
   qualitative findings, limitations, and reproducibility.
6. **Responsible AI note.** Link or upload `docs/RESPONSIBLE_AI.md`, covering
   consent, redaction, pseudonymization, retention, deletion, grounding, candidate
   incident review, and dataset limits.
7. **Optional benchmark-audio bonus.** A Hugging Face dataset link containing only
   publishable, de-identified synthetic domain audio plus metadata and provenance.
   AfriSwitch audio must follow its access and licence terms and should not be
   republished casually.

## Five-Minute Video Story

- **0:00–0:30:** the problem and one-line solution.
- **0:30–1:35:** a code-switched Tier 1 call finds a verified fault, explains the
  ETA, and queues an allowed callback or compensation.
- **1:35–2:35:** a Tier 2 call uses account state and an approved playbook, then
  waits for the caller's result.
- **2:35–3:25:** the third distinct unresolved complaint creates a ticket and an
  **unconfirmed** candidate incident visible in operations.
- **3:25–4:25:** show the benchmark headline: 400 natural clips, four ASR models,
  200 TTS outputs, three judges, four languages, and the downstream score.
- **4:25–5:00:** show privacy evidence, reproducibility hashes, impact, and the
  closing claim.

Do not spend video time scrolling through code. Show one short tool trace to prove
that the agent used verified state, then use clear result visuals.

## Files to Finish Before Upload

- `docs/DEMO_SCRIPT.md`: exact spoken phrases, seed state, clicks, and fallback
  recording plan.
- `docs/BENCHMARK_REPORT.pdf`: complete and visually checked at three A4 pages.
- `benchmark/results/agent_audio_summary.json`: complete with 360 raw runs.
- `docs/RESPONSIBLE_AI.md`: final review against demonstrated behavior.
- README: final Railway, YouTube, report, and Hugging Face links.
- GitHub release or immutable commit tag used by every submitted link.

The submission is therefore a **working product plus evidence**, not only a
frontend: deployed application, video, source code, three-page benchmark PDF,
Responsible AI note, and optional public benchmark audio.
