# FaultBridge

FaultBridge is a code-switched voice support agent for Nigerian mobile networks.
It turns a caller's complaint into a verified answer, a safe action, and useful
network evidence.

![FaultBridge caller support interface](docs/assets/faultbridge-caller.webp)

## Why FaultBridge Matters

A telco may know about a fibre cut before its customers do, yet every caller still
explains the same outage from scratch. FaultBridge connects the customer support
call to verified NOC and account data. It supports Pidgin-English, Hausa-English,
Igbo-English, and Yoruba-English.

The scale and channel are measurable:

- Of 3,019 complaints received by the NCC in Q1 2021, 91.4% arrived through its
  voice contact centre, which manages the 622 toll-free line. Billing, voice
  quality, and data quality were the leading complaint types
  ([Voice of Nigeria](https://von.gov.ng/ncc-resolves-99percent-telecom-consumer-complaints-in-q1-2021/)).
- Nigeria recorded 19,384 fibre cuts between January and August 2025. The NCC said
  these disruptions caused prolonged outages and delayed restoration
  ([BusinessDay](https://businessday.ng/news/article/ncc-records-over-19000-fibre-cuts-in-8-months-maida/)).
- More than 75 million affected subscribers received compensation after an NCC
  service-quality directive
  ([The Guardian Nigeria](https://guardian.ng/featured/telcos-compensate-75-million-subscribers-says-ncc/)).

The language gap is also an industry priority. The GSMA, Airtel, MTN, Masakhane,
and other partners formed a continent-wide initiative for inclusive African
language models ([GSMA](https://www.gsma.com/newsroom/press-release/gsma-africas-leading-mobile-operators-and-the-ai-ecosystem-unite-to-accelerate-development-of-inclusive-african-ai/)).
At the network layer, the ITU's €35,000 AI Telco Troubleshooting Challenge applies
language models to root-cause analysis of telecom faults
([ITU AI for Good](https://aiforgood.itu.int/ai-telco-troubleshooting-challenge/)).
FaultBridge carries verified fault knowledge to customers and sends recurring,
unresolved customer evidence back to network operations.

## What the Agent Does

1. Sahara transcribes the caller with an explicit language selection.
2. FaultBridge redacts personal identifiers before model analysis or storage.
3. A structured LLM extracts the issue without receiving authority to run tools.
4. The policy engine checks the exact cell, account state, and approved playbooks.
5. It queues an idempotent callback or compensation command when policy permits.
6. Unresolved complaints become tickets and distinct-caller network signals.
7. Three matching unresolved callers can propose an **unconfirmed** NOC incident.
8. Sahara speaks the grounded response in the caller's selected language.

This is an agentic workflow because each call selects a resolution tier, invokes
typed tools, changes durable operational state, verifies outcomes, and either
resolves the request or creates a structured handoff. Repeated unresolved calls
form an evidence-gated candidate incident for NOC review.

The submission uses Sahara for speech and Together-hosted Llama 3.3 70B for
structured complaint analysis. Speech, model, and telephony implementations sit
behind provider interfaces.

## Run the Working Prototype

Install Docker and [uv](https://docs.astral.sh/uv/), then:

```bash
cp .env.example .env
# Set strong local secrets plus SAHARA_API_KEY and TOGETHER_API_KEY.
make docker-up
make demo-seed
```

Open `http://localhost:8010/` for caller support and
`http://localhost:8010/operations` for the protected operations workspace.
`make demo-seed` loads a labelled synthetic incident and account through the
same authenticated ingestion API used by real integrations.

```bash
make test           # run 90 unit and PostgreSQL integration tests
make lint           # check formatting and static rules
make docker-status  # inspect container health
make docker-down    # stop the local stack
```

No separate frontend service is required. The FastAPI container serves both
responsive web interfaces.

## Architecture

```mermaid
flowchart LR
    A[Caller audio] --> B[Sahara STT]
    B --> C[PII redaction]
    C --> D[Structured LLM analysis]
    D --> E[Constrained policy engine]
    E --> F[PostgreSQL tools]
    F --> G[Audited actions and signals]
    E --> H[Sahara TTS]
```

Only the policy engine can invoke tools. Confirmed outage answers require an exact
match against a verified incident record. Approximate retrieval is never used as
proof of a fault. Read [Architecture](docs/ARCHITECTURE.md) and
[Benchmark Methodology](docs/BENCHMARK_METHODOLOGY.md) for the boundaries,
tradeoffs, and evaluation design.

## Benchmark Evidence

The [three-page report](docs/BENCHMARK_REPORT.pdf) evaluates components and the
complete agent:

| Track | Evidence | Headline result |
| --- | ---: | --- |
| Natural ASR | 400 AfriSwitch clips, 4 systems | Sahara 55.0% equal-language WER |
| Code-switched TTS | 200 Sahara outputs, 3 ASR judges | 200 of 200 generated |
| Agent task execution | 648 LLM and PostgreSQL runs | Sahara transcript path 100% strict success |
| Privacy | 100 labelled synthetic cases | 100% exact typed-span F1 within scope |

Failures and empty transcripts remain in the denominator. Raw JSONL contains
provider metadata, hashes, latency, and error records so aggregates can be
recomputed. The natural-audio evidence is private because AfriSwitch access terms
must be preserved:
[`Tiamz/faultbridge-asr-benchmark-evidence`](https://huggingface.co/datasets/Tiamz/faultbridge-asr-benchmark-evidence),
revision `ef320d7f367e040c47b4021a397011dae894fe00`.

Automatic TTS scores are diagnostic signals. A qualified bilingual listening
audit remains pending, so this project makes no MOS or human-quality claim.
Commands and metric definitions are in [eval/README.md](eval/README.md), with the
full explanation in the
[Technical Guide](docs/FAULTBRIDGE_TECHNICAL_GUIDE.md).

## Submission Materials

- [Benchmark report](docs/BENCHMARK_REPORT.pdf)
- [Benchmark methodology](docs/BENCHMARK_METHODOLOGY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Technical guide](docs/FAULTBRIDGE_TECHNICAL_GUIDE.md)
- [Responsible AI note](docs/RESPONSIBLE_AI.md)

The final local video master is
`artifacts/demo-video/FaultBridge-Intron-Demo.mp4`. Generated media is ignored
by Git; the submitted YouTube URL should point to this verified 4 minute 47 second
cut.

## Data and Security Boundary

The repository contains no real subscriber, account, incident, or caller records.
Raw call audio stays in memory. Stored callers are pseudonymous, transcripts are
redacted, and authenticated deletion and retention controls are implemented.
Credentials belong only in the ignored `.env` file. Review
[Responsible AI](docs/RESPONSIBLE_AI.md) before connecting a real operator system.

## License

Copyright © 2026 Hamzat Tiamiyu. All rights reserved. No permission is granted for
use, copying, modification, redistribution, deployment, or commercial
exploitation. See the [proprietary license](LICENSE) for the complete terms.
