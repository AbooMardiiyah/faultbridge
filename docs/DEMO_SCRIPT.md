# FaultBridge Demo Script

The verified local master is
`artifacts/demo-video/FaultBridge-Intron-Demo.mp4`. It runs for 4 minutes
47 seconds and uses Nigerian English narration. The Pidgin caller scene contains
a real Sahara STT request, real application execution, and the returned Sahara
TTS audio. Its small captions appear only while the caller or Sahara is speaking
and sit below the interface.

## 0:00 to 0:19 | Open With the Gap

**Show:** FaultBridge title card.

**Say:** “A telco may know a fibre cut happened before its customers do. Yet
every caller still explains the same outage from scratch. I am Hamzat, and this is
FaultBridge: a code-switched voice support agent that turns one complaint into a
verified answer, a safe action, and usable network evidence.”

## 0:19 to 0:44 | Establish Trust

**Show:** Caller support with Pidgin-English selected, consent checked, area
`Evaluation Area 02`, cell `EVAL-002`, and synthetic number `08030000002`.

Explain that FaultBridge supports four language pairs, obtains consent, redacts
identifiers, and checks verified network state before taking action.

## 0:44 to 1:18 | Run the Voice Call

Press **Start speaking** and say:

> Abeg, wetin dey happen to the network for this area? I don off and on my phone
> tire, but signal still no dey since morning. I consent to automated processing.

Press **Stop recording**. Wait for **Complete**, then press **Play response**.
Point out the transcribed complaint, confirmed fibre cut, natural West Africa Time
estimate, queued 500 MB credit, and scheduled service update.

The wording follows common Nigerian telco complaint structure: location, duration,
failed restart, and remaining symptom. It contains no copied identity or phone
number. Public context includes reported no-signal complaints after phone restarts
in [Business A.M.](https://www.businessamlive.com/wp-content/uploads/2025/03/371-17-March-23-March-2025.pdf)
and broader connectivity complaints summarized by
[X](https://x.com/i/trending/1819696088829534387?lang=en).

## 1:18 to 1:41 | Show Network Value

Open **Operations**. Show recent calls, queued actions, and the four-stage path
from speech to verified action. Explain that operational records contain a
pseudonymous caller and redacted transcript.

## 1:41 to 2:37 | Defend the Agent

Open **Review trace** for the newest call. Point to:

1. verified network fault match with NOC provenance;
2. authoritative account check;
3. idempotent compensation command;
4. restoration callback command.

Explain the two other paths. An unknown fault uses an approved troubleshooting
playbook and waits for caller verification. A failed verification opens a
specialist handoff. Three distinct unresolved callers can propose an
**unconfirmed** incident for NOC review.

## 2:37 to 4:39 | Present the Benchmark

Show the three pages of `docs/BENCHMARK_REPORT.pdf`.

- **Natural ASR:** 400 hash-frozen AfriSwitch clips, 100 per language pair, sent
  to four systems. Empty outputs remain failures. Sahara achieved the lowest
  equal-language WER at 55.0%.
- **TTS and downstream task:** Sahara generated all 200 female and male outputs.
  Three independent ASR families measured transcript fidelity. Across 648 real
  LLM and PostgreSQL runs, Sahara transcripts produced 100% strict task success.
  All four ASR paths had zero critical safety failures.
- **Privacy and reproducibility:** 100 labelled synthetic cases achieved 100%
  exact typed-span F1 within the declared deterministic scope. Raw JSONL, hashes,
  failures, model versions, and aggregate verification commands are retained.

State the limitation clearly: automatic TTS scores are diagnostic, while the
qualified bilingual listening audit remains pending.

## 4:39 to 4:47 | Close

**Say:** “FaultBridge turns code-switched customer calls into grounded help for
callers and usable evidence for network teams. Thank you.”

## Before You Re-record

```bash
make docker-up
make demo-seed
make docker-status
```

Use 100% browser zoom, close notifications, and enter the internal access key off
camera. Use only the synthetic details above. Keep the final cut below five
minutes and never replace a failed provider request with a fabricated response.
