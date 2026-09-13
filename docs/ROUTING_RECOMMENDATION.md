# Evidence-Based ASR Routing Recommendation

## Decision

Use Sahara as FaultBridge's single speech-recognition provider for the Intron
submission. Do not activate language-based multi-ASR routing yet. If recognition
fails or produces an unusable complaint, ask the caller to repeat once and then
offer human escalation.

## Evidence

On the equal-language 400-clip natural AfriSwitch panel, Sahara had the lowest
WER for Hausa-English, Igbo-English, and Pidgin-English. The small Yoruba-English
WER advantage observed for OmniASR or SBPN was inconclusive under the paired 95%
bootstrap intervals.

The named-ASR downstream panel strengthens the decision. Sahara preserved 100%
of gold-transcript agent task success, compared with 95.8% for SBPN, 87.5% for
OmniASR, and 79.2% for Faster-Whisper. All models passed the critical safety
gates, but safety alone does not justify switching to a less reliable task path.

The local comparison models also lack like-for-like deployed p95 post-audio
latency. Local inference time and Sahara file-API time are different measurements,
so the routing gate treats missing comparable latency as a rejection rather than
assuming it passes.

## What “Intelligent Routing” Means Here

The router is an evidence gate, not an extra model. A non-Sahara primary is
allowed only when it has a statistically supported paired WER improvement, stays
inside the 1% provider-failure and two-second p95 budgets, and records zero
critical downstream failures. No current alternative meets all conditions.

Re-run `make benchmark-route` after deploying a comparator and collecting matched
streaming latency and reliability. The machine-readable result is
`benchmark/results/routing_policy.json`. This keeps the architecture ready for
future routing without adding an unjustified model, GPU service, or failure mode
to the hackathon demo.
