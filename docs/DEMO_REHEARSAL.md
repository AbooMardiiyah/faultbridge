# FaultBridge Demo Rehearsal

Use `artifacts/demo-video/FaultBridge-live-Pidgin-call.mp4` as the exact reference
for the live section. Keep the internal key and `.env` outside the recording.

## Before Recording

1. Run `make docker-up` and confirm both services are healthy.
2. Open `http://localhost:8010/` at 100% browser zoom.
3. Select `Pidgin + English`.
4. Enter area `Evaluation Area 02`, cell `EVAL-002`, and callback number
   `08030000002`.
5. Check **I agree to voice processing** and enter the internal access key under
   **Demo access**.

## Live Caller Scene

Press **Start speaking**, wait for the red **Stop recording** state, and say:

> Abeg, wetin dey happen to the network for this area? I don off and on my phone
> tire, but signal still no dey since morning. I consent to automated processing.

Press **Stop recording**. Do not speak while **Checking the evidence** is shown.
Wait for **Complete**, then point out the transcript, grounded fibre-cut answer,
and the network, account, compensation, and callback action cards. Press
**Play response** so the judges hear Sahara TTS.

## Operations and Evidence

Select **Operations**, unlock the workspace, and open the newest call with
**Review trace**. Point to the PII-safe transcript, verified incident source,
account check, queued credit, and callback. Then show the three pages of
`docs/BENCHMARK_REPORT.pdf`: natural ASR, TTS and agent outcomes, then privacy and
reproducibility. Finish on the FaultBridge closing card.

If Sahara returns a temporary error, stop recording and retry later. Do not replace
the live call with a response that did not pass through the voice endpoint.
