# Demo Rehearsal

Watch `artifacts/demo-video/FaultBridge-Intron-Demo.mp4` and follow
[the exact script](DEMO_SCRIPT.md). The master is a scene-by-scene reference, not
just a visual montage.

## Setup

1. Run `make docker-up`, `make demo-seed`, and `make docker-status`.
2. Open `http://localhost:8010/` at 100% zoom.
3. Select `Pidgin + English`.
4. Enter `Evaluation Area 02`, `EVAL-002`, and `08030000002`.
5. Check consent and enter the internal key under **Demo access** off camera.
6. Keep `/operations` and `docs/BENCHMARK_REPORT.pdf` ready in other tabs.

## Live Sequence

Speak the exact Pidgin complaint in the script, then stop recording. Wait without
speaking while **Checking the evidence** appears. After **Complete**, show the
transcript and action cards, then select **Play response**. Sahara should read a
normal clock phrase such as “1:30 AM West Africa Time,” rather than an ISO
timestamp.

In Operations, open the newest call. Confirm that its call time and transcript
match the live run before showing the four persisted tool events.

## Quality Check

- The caller and Sahara captions begin with their audio and never cover the UI.
- No key, token, browser notification, real phone number, or unrelated tab appears.
- The result says **known fault confirmed** and the operations trace shows the same
  call.
- Benchmark numbers match the three-page PDF.
- The exported video is below five minutes and the YouTube link works while signed
  out.

If Sahara returns a temporary provider error, stop the recording and retry later.
Keep the last successful real call as the fallback.
