# Industry-Grade Voice Application Benchmark for FaultBridge

## Executive Decision

FaultBridge should be evaluated as a complete decision system and as a set of
diagnosable components. Word Error Rate (WER) remains necessary because it is
widely understood, reproducible, and explicitly requested by Intron. It is not a
sufficient measure of a code-switched telco agent: one incorrect cell identifier
can be more damaging than several harmless function-word errors, and a fluent
transcript can still cause an unsupported outage claim or an unauthorized account
action.

The winning benchmark therefore has two linked tracks:

1. **Code-switched ASR track:** Sahara, SBPN Multilingual Base, Meta omniASR CTC
   300M, Faster-Whisper, and AssemblyAI Whisper Streaming receive the same audio
   under the same audio and normalization policy. Results include raw and
   normalized WER/CER, language-role error, code-switch preservation, critical
   entity recall, latency, failure rate, and robustness slices.
2. **End-to-end agent track:** the gold transcript and every model hypothesis pass
   through the same frozen FaultBridge agent and PostgreSQL scenario. Executable
   assertions grade the selected tier, tool sequence, arguments, database state,
   spoken claims, privacy behavior, and final outcome.

This design isolates ASR-caused loss by comparing each model's downstream score
with the gold-transcript upper bound. It also makes intelligent routing defensible:
route only when paired evidence shows a material improvement without worse safety,
latency, or cost.

## What Industry Benchmarks Actually Measure

Traditional ASR evaluation aligns a reference transcript and hypothesis and counts
substitutions, deletions, and insertions. NIST's OpenASR evaluation applies a fixed
normalization before scoring with `sclite`, reinforcing that normalization is part
of the benchmark definition rather than a cleanup choice made after results are
seen.^1 Intron's own public framework reports both normalized and unnormalized WER
and CER, with results separated by language and model.^2

Research on code-switching shows why a single WER can mislead. PolyWER permits
alternative transliterations or translations where multiple renderings are valid.^3
Point-of-Interest Error Rate (PIER) focuses scoring on the switched words that a
global average can hide.^4 Work on bilingual ASR also reports matrix-language and
embedded-language performance separately. Meaning-based measures such as BERTScore
can complement WER when orthographic variation preserves meaning, although they
must not replace transparent lexical scores.^5

Modern voice-agent benchmarks add interaction and execution. VoiceBench varies
speakers, environments, and content instead of testing only clean speech.^6
VoiceAgentBench scores tool selection, argument structure, multi-tool workflows,
multi-turn behavior, and adversarial robustness.^7 The text-agent benchmark
τ-bench checks the final database state and uses repeated-run reliability rather
than assuming one successful run proves dependable behavior.^8 τ-Voice carries the
same tasks and deterministic database evaluator into full-duplex calls, then adds
telephony compression, noise, dropped frames, diverse voices, and controlled
interruptions. Its comparison with the text baseline motivates reporting how much
task capability survives the voice channel.^23 Recent end-to-end voice work goes
further: VAmoS jointly grades transcripts, tool calls, returned rows, spoken
claims, and state changes,^9 while EVA-Bench separates accuracy from experience
and includes accent/noise perturbations plus repeated-run measures.^10

Voice quality and timing need their own evidence. ITU-T P.808 defines a
crowdsourcing approach for subjective speech-quality evaluation,^11 P.863 defines
objective perceptual speech-quality prediction,^12 and G.107 models the combined
effects of codecs, packet loss, noise, echo, and delay on conversational quality.^13
For browser calls, the W3C WebRTC statistics model exposes packet loss, jitter,
round-trip time, discarded packets, and jitter-buffer delay.^14 End-of-turn
benchmarks demonstrate the central tradeoff: measure response delay at a fixed
false-interruption budget, because an aggressively fast agent can achieve low
latency by cutting callers off.^15

## Evaluation Questions

The benchmark should answer six questions in order:

1. How accurately does each model transcribe each Nigerian code-switched language
   pair?
2. Does the model preserve switched English spans, local-language spans, telecom
   terms, locations, numbers, and negation?
3. How much ASR error propagates into symptom classification, evidence lookup,
   tool use, and resolution outcomes?
4. Does the complete voice loop respond quickly and handle pauses, interruptions,
   telephone codecs, background noise, and provider failures?
5. Does it protect PII, obtain consent, avoid unsupported claims, and escalate when
   automation is unsafe?
6. Are results consistent across language pairs and repeated runs, with uncertainty
   shown rather than hidden by one aggregate average?

## Dataset Design

### Natural code-switched core

AfriSwitch is the primary ASR test source. Its dataset card describes 54.41 hours,
16,602 utterances, 14 African languages switching with English, human transcripts,
English-span tags, Code-Mixing Index (CMI), switch counts, duration, and 16 kHz
audio. It provides a single evaluation-only `test` split under CC BY-NC-SA 4.0.^16
FaultBridge uses the Hausa, Igbo, Nigerian Pidgin, and Yoruba configurations.

For the deadline-constrained primary panel, select **400 clips: 100 per language
pair**. Use a fixed random seed and stratify within each language by:

- CMI: low, medium, and high mixing;
- switch count: 1–2, 3–5, and 6+ transitions;
- duration: short, medium, and long thirds;
- audio quality or estimated SNR where available;
- source recording group inferred from the source filename, to reduce correlated
  segments dominating a stratum.

Freeze the selected sample IDs and publish their SHA-256 manifest before model
comparison. Never remove clips because a provider failed. A failed or empty
transcription remains in the denominator. If quota and time permit, run all four
language configurations as a sensitivity analysis; keep the 400-clip panel as the
predeclared primary comparison.

AfriSwitch does not expose enough speaker demographics for demographic fairness
claims. Report language, CMI, duration, source, and signal-condition slices, and
state explicitly that gender, age, rurality, and individual-speaker parity cannot
be concluded from this corpus. This is important because published ASR audits have
found large performance disparities between speaker groups, demonstrating why a
pooled score cannot establish fairness.^17

### Telco task set

Create a separate, versioned domain evaluation set of **48 scenarios: 12 per
language pair**. It should cover all three resolution tiers and the failure paths:

| Scenario family | Required variations | Strict expected result |
|---|---|---|
| Verified outage | cause present/absent, ETA present/absent, eligible/ineligible account | Correct incident only; no invented cause/ETA; action queued only when eligible |
| Individual account | no balance, barred line, healthy account | Correct account branch; no outage claim |
| Guided diagnosis | approved playbook, missing playbook, unsupported request | Only verified playbook steps; verification requested |
| Escalation | failed fix, missing account, ambiguous symptom | Ticket and safe summary; no fabricated resolution |
| Crowd signal | distinct and duplicate callers around threshold | Candidate only at distinct-caller threshold; always marked unconfirmed |
| Safety/privacy | declined consent, spoken phone/NIN/account, adversarial request | Stop or redact; no unauthorized tool or PII leakage |

The scenarios should execute against isolated PostgreSQL state through the same
production APIs and tools. Synthetic operational records are acceptable when they
are labelled as evaluation records and never presented as operator data. This is a
controlled test environment, not simulated application behavior: tools execute
real queries and commits, and graders inspect the resulting state.

Use natural recordings as the primary domain audio when consent and bilingual
speakers are available. Sahara TTS variants can expand acoustic coverage, but
should be a separately labelled secondary set. Using one evaluated vendor's TTS as
the only source would introduce a vendor-specific synthesis confound. Every clip
needs provenance, consent status, source type, language pair, codec, duration,
noise condition, and reference annotations.

### Development and test separation

Do not tune prompts, normalization rules, routing thresholds, or playbooks on the
AfriSwitch evaluation panel. Develop against separate authored telco examples and
provider documentation. Freeze these items before the first scored run:

- sample manifest and reference revision;
- model identifiers and API parameters;
- normalization implementation and exception map;
- audio conversion and chunking policy;
- scenario database snapshots and assertions;
- agent prompt, playbooks, and routing policy;
- metric definitions and aggregation rules.

Any later correction creates a new benchmark version and reruns every provider.

## ASR Measurement

### Frozen model panel

The guaranteed comparison is Sahara Streaming STT, the Nigeria-specific SBPN
Multilingual Base 120M, Meta `omniASR_CTC_300M_v2`, and Faster-Whisper `large-v3`.
AssemblyAI Whisper Streaming (`whisper-rt`) adds a commercial streaming sensitivity
comparison when credentials are available. This exceeds the stricter challenge
page wording of Sahara plus at least three alternatives and contrasts African,
Nigerian, massively multilingual, and global model families rather than several
wrappers around the same model.^20 SBPN Base is a 120M-parameter Nigerian model
covering Yoruba, Hausa, Igbo, Nigerian Pidgin, and Nigerian English.^22

AssemblyAI's Universal streaming family does not list the four Nigerian languages,
so it is not used on the primary panel. Whisper Streaming lists Hausa and Yoruba
but not Igbo or Nigerian Pidgin; those unsupported-language results remain in the
denominator and are identified in the report.^19 Record the provider model
identifier returned or configured at run time and treat any provider-side model
update as a new benchmark run. Sahara stays the product default for the Intron
submission regardless of the comparison result; the benchmark measures where a
later routing policy could help.

### Primary lexical scores

Report corpus-level micro WER as:

`WER = (substitutions + deletions + insertions) / reference words`.

Also report macro WER across utterances so a few long clips cannot conceal poor
short-call performance. CER provides a useful complement for agglutinative words,
spelling variation, and tokens that word segmentation handles poorly. Report:

- raw WER and CER after Unicode canonicalization only;
- normalized WER and CER after the frozen Intron-aligned policy;
- substitution, deletion, and insertion rates separately;
- empty-output and provider-error rate;
- per-language macro and micro scores plus an equal-language macro average.

The normalized policy should use Unicode NFKC, lowercase, whitespace collapse,
documented punctuation removal, and a published number policy. Run a parallel
diacritic-preserving score and a diacritic-insensitive sensitivity score. Do not
silently correct model spelling with an LLM. If multiple local spellings are
accepted, publish the equivalence mapping and use it for all systems.

### Code-switch scores

AfriSwitch's `[[EN]]...[[/EN]]` spans enable a more revealing scorecard:

- **Embedded-English PIER:** error rate on reference tokens inside English spans.
- **Matrix-language token error:** error rate on reference tokens outside English
  spans.
- **Language-role gap:** absolute difference between embedded and matrix error.
- **Switch-context preservation:** proportion of switch boundaries for which both
  neighboring reference tokens appear correctly and adjacently in the hypothesis.
- **Performance by CMI and switch-count band:** shows whether quality collapses as
  mixing becomes denser.

True switch-boundary precision requires language labels on hypothesis tokens.
Automatic language identification is weak for short borrowed words and Nigerian
Pidgin, so do not report a misleading automatic F1 as ground truth. Instead,
double-annotate a balanced subset of 80 hypotheses with bilingual reviewers and
report boundary precision, recall, F1, agreement, and adjudication rules there.

### Semantic and critical-content scores

Report a multilingual semantic similarity score as supporting evidence only.
Lexical scores remain primary because embedding metrics can award a fluent
paraphrase that changes an account number or negation. Add deterministic measures
that reflect the telco task:

- critical entity precision/recall/F1 for location, operator, cell identifier,
  amount, duration, phone/account placeholder, and device;
- negation preservation accuracy;
- telecom keyword recall;
- symptom classification macro-F1 when the frozen analyzer consumes each
  hypothesis.

Named entities should be matched after type-specific canonicalization: case folding
for locations, digit normalization for amounts, and exact normalized matching for
cell/account identifiers. A model gets no entity credit for semantically similar
digits.

## End-to-End Agent Measurement

### Gold-versus-ASR counterfactual

Run every domain scenario once with its human reference transcript to establish the
agent's text-input upper bound. Then replace only the transcript with each ASR
hypothesis while holding the agent model, prompt, operational state, playbooks, and
tools constant. For model `m`:

`ASR propagation loss(m) = task success(gold) - task success(hypothesis_m)`.

Also report **voice capability retention**:

`retention(m) = task success(hypothesis_m) / task success(gold)`.

This makes the cost of the voice channel easy to communicate while the absolute
scores and propagation loss prevent a weak gold-text baseline from looking good.

This separates an agent-policy failure from a speech-recognition failure. Report
both values; a high ASR score cannot excuse a weak agent, and a strong agent can
demonstrate robustness to harmless transcription errors.

### Executable task grading

Each scenario contains binary assertions over the complete trace and final
database state. Grade at least:

- correct resolution tier;
- correct tool names, order, count, and typed arguments;
- correct incident/account/playbook row used;
- required ticket, callback, compensation, or candidate row created;
- prohibited rows absent;
- spoken outcome consistent with returned tool evidence;
- correct resolution, escalation, refusal, or redirect.

The primary downstream metric is **strict task success**: all required assertions
pass and no safety-critical assertion fails. Also report component assertion pass
rates for diagnosis. This follows the state-based logic used by τ-bench and the
joint trace/state approach used by end-to-end voice-agent benchmarks.^8,9

“Containment” should not mean avoiding human escalation at any cost. Report
**appropriate automation rate**: calls correctly resolved automatically divided by
calls eligible for automatic resolution. Report **appropriate escalation recall**
for cases that require a person. An unsafe automatic completion counts as failure,
not successful containment.

Run stochastic agent scenarios three times. Report pass@1, pass@3, and pass^3:
whether at least one run succeeds and whether all three succeed. Reliability is
especially important for compensation, privacy, and outage claims.

### Independent conversation evaluation

If access is available, run the deployed agent through Cekura as a supplementary
black-box check. Freeze 10–20 scenarios derived from the reviewed telco set and
retain its transcripts, evaluator rubrics, and failures. Treat this as independent
evidence for multi-turn quality and regression discovery, not as a replacement for
the AfriSwitch manifest, deterministic privacy gates, or PostgreSQL state
assertions. The Pipecat hackathon starter demonstrates this iterate-from-report
workflow and records pipeline TTFB metrics, but it does not define a comparative
code-switch dataset benchmark.^21

### Safety and groundedness

Use deterministic critical gates alongside human review:

- verified-outage false-positive rate;
- unsupported cause or ETA claim rate;
- unauthorized compensation rate;
- candidate-presented-as-confirmed rate;
- consent violation rate;
- PII leakage rate in prompts, stored transcripts, events, summaries, and replies;
- correct idempotency under repeated calls and delivery retries.

The launch target for each of these critical rates is zero on the fixed test set.
Do not combine them into an average that allows a latency or fluency gain to offset
a harmful action.

## Real-Time Voice Experience

### Timestamped latency budget

Instrument monotonic timestamps at each boundary:

1. first inbound audio byte;
2. detected end of caller speech;
3. first and final STT result;
4. agent request and first model token/decision;
5. each tool request and result;
6. first TTS audio byte;
7. first audio byte sent to the caller;
8. turn completion.

Report p50, p90, p95, and maximum for STT finalization, agent decision, tool work,
TTS first byte, and end-of-speech-to-first-agent-audio. Means alone conceal the
long pauses users remember. Measure cold and warm startup separately and disclose
client location, provider region if known, connection type, time window, and retry
policy.

Endpointing and barge-in need paired metrics:

- end-of-turn delay at a fixed false-cutoff budget;
- false interruption rate on mid-turn pauses;
- missed interruption rate;
- time from caller barge-in to agent audio stop;
- repeated-word or lost-context rate after interruption.

The fixed-budget view follows current end-of-turn benchmarking practice: speed and
false cutoff are a Pareto tradeoff, so reporting either alone rewards bad behavior.^15

### Audio and network robustness

Preserve the original clean clip, then derive controlled variants from that same
clip:

- PSTN-like 8 kHz μ-law encode/decode;
- 16 kHz clean PCM reference;
- environmental noise at 20, 10, and 5 dB SNR;
- mild reverberation;
- packet loss at 1%, 3%, and 5%, including a burst-loss condition;
- jitter/delay profiles for stable Wi-Fi and constrained mobile data.

Use identical transforms and seeds for every model. Report degradation relative to
each model's clean score rather than only absolute noisy scores. For browser calls,
capture W3C statistics for packet loss, jitter, round-trip time, discarded packets,
and jitter-buffer delay.^14 For phone calls, state the carrier, codec, route, and
country; do not compare a direct WAV upload for one provider with PSTN audio for
another.

### Output speech quality

TTS is evaluated separately from ASR model ranking. Use bilingual listeners and an
ITU-T P.808-style protocol for naturalness, intelligibility, pronunciation of local
names, language appropriateness, and listening effort.^11 Randomize and blind
system identity. Include comprehension questions for cause, ETA, action, and ticket
number; an attractive voice that communicates the wrong fact must fail task
fidelity.

If a licensed P.863 implementation is available, report objective listening
quality as supporting evidence.^12 Otherwise do not label an open approximation as
POLQA. At minimum report audio-generation failures, duration ratio, clipping,
silence, and native-review scores.

## Privacy, Inclusion, and Human Review

NIST's AI Risk Management Framework calls for documented, repeatable evaluation,
uncertainty, deployment-relevant conditions, privacy measurement, and fairness
measurement.^18 FaultBridge should make these visible:

- score PII redaction precision, recall, F1, and per-type false negatives;
- treat caller-data leakage as a critical failure even if redaction precision is
  otherwise high;
- report consent adherence and deletion completeness;
- publish every metric by language pair and available acoustic slice;
- never infer demographic fairness from missing demographic metadata;
- have two bilingual reviewers independently score the qualitative subset;
- report agreement, resolve disagreements through adjudication, and preserve the
  rubric with anonymized ratings.

Human review should focus on errors automatic metrics cannot settle: valid spelling
variants, mixed-language naturalness, preserved meaning, politeness, harmful
certainty, and whether the response sounds locally appropriate. Reviewers should
not know which ASR produced a hypothesis.

## Statistical Analysis and Reproducibility

Use paired comparisons because every model processes the same clips. Report 95%
confidence intervals from at least 2,000 bootstrap resamples, sampling source groups
within each language so adjacent clips from one recording do not create false
precision. For WER, recompute the corpus numerator and denominator inside every
resample. For task success and entity F1, recompute the metric rather than averaging
precomputed intervals.

Publish paired confidence intervals for model differences, not only separate model
intervals. Avoid declaring a winner when the paired interval crosses zero. For four
language pairs, always show per-language results and an equal-language macro score;
the pooled micro score is secondary.

Every result row should retain:

- benchmark and manifest version;
- sample ID and audio SHA-256;
- provider, exact model identifier, region, and parameters;
- request start, partial, final, and failure timestamps;
- raw provider response in a private ignored directory;
- normalized hypothesis and normalization version;
- retry count, HTTP/provider status, and cost metadata;
- code commit and environment lock hash.

Release the sample-selection script, manifests without restricted content,
normalizer, scorer, scenario definitions, aggregate results, and report. Keep API
keys, raw PII, restricted audio, and provider payloads out of Git.

## Intelligent Routing Decision Rule

Routing is an output of the benchmark. For each language/condition cell, a provider
is eligible only if it:

1. improves paired downstream task success or critical-entity recall;
2. has a confidence interval that supports the improvement;
3. does not worsen any critical safety gate;
4. meets the p95 latency and failure-rate budget;
5. has acceptable cost per correctly handled call.

Use a simple versioned policy table in PostgreSQL, with a conservative Sahara
default and fallback on provider failure. Do not route token-by-token between ASRs:
that introduces alignment and context errors. Route a whole utterance based on
known language pair and operating condition. The Intron demo remains Sahara
end-to-end; routing results can be shown as a measured product insight and enabled
later where competition rules permit.

## Three-Page Submission Report

The detailed benchmark belongs in the repository; the submission PDF should be
compressed around judge decisions.

**Page 1 — Data and method**

- four language pairs, sample counts, minutes, source, license, and stratification;
- three ASR models and exact versions;
- frozen normalization and audio conditions;
- diagram of audio → ASR → identical agent → PostgreSQL assertions;
- WER/CER and downstream-task definitions.

**Page 2 — Quantitative evidence**

- per-language normalized WER table with 95% intervals;
- embedded versus matrix-language error and language-role gap;
- critical-entity F1 and strict task-success table;
- p50/p95 latency and provider failure rate;
- one compact robustness chart by CMI or telephone condition.

**Page 3 — Findings, safety, and product decision**

- three concrete failure examples showing harmless versus consequential errors;
- gold-transcript upper bound and ASR propagation loss;
- privacy/groundedness critical-gate table;
- measured routing decision and why Sahara remains the Intron product default;
- limitations: sample size, missing demographics, synthetic domain variants, and
  incomplete live-operator validation.

This presentation exceeds a cheap leaderboard because it connects code-switch
recognition to actual customer and operator outcomes, quantifies uncertainty, and
shows where every conclusion stops.

## Sources

1. NIST. “[OpenASR21 Evaluation Plan](https://www.nist.gov/system/files/documents/2021/08/31/OpenASR21_EvalPlan_v1_3_1.pdf).” 2021.
2. Intron Innovation. “[Intron Multimodal Benchmarking](https://github.com/intron-innovation/Intron-Multimodal-Benchmarking).” 2026.
3. Kadaoui et al. “[PolyWER: A Holistic Evaluation Framework for Code-Switched Speech Recognition](https://aclanthology.org/2024.findings-emnlp.356/).” Findings of EMNLP, 2024.
4. Herb and Hübner. “[PIER: A Novel Metric for Evaluating What Matters in Code-Switching](https://ieeexplore.ieee.org/document/10889660/).” ICASSP, 2025.
5. Tobin et al. “[Assessing ASR Model Quality on Disordered Speech Using BERTScore](https://research.google/pubs/assessing-asr-model-quality-on-disordered-speech-using-bertscore/).” S4SG, 2022.
6. Chen et al. “[VoiceBench: Benchmarking LLM-Based Voice Assistants](https://arxiv.org/abs/2410.17196).” TACL, 2026.
7. Jain et al. “[VoiceAgentBench: Are Voice Assistants Ready for Agentic Tasks?](https://arxiv.org/abs/2510.07978).” 2026 revision.
8. Yao et al. “[$\tau$-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains](https://openreview.net/pdf?id=57cd0f8d1f7b7790714c1bedf5d781ba10e56590).” ICLR, 2025.
9. Meyer et al. “[VAmoS Bench: Voice Agent Simulation Bench](https://arxiv.org/abs/2607.27453).” 2026.
10. Bogavelli et al. “[EVA-Bench: A New End-to-End Framework for Evaluating Voice Agents](https://arxiv.org/abs/2605.13841).” 2026.
11. ITU-T. “[P.808: Subjective Evaluation of Speech Quality with a Crowdsourcing Approach](https://www.itu.int/ITU-T/recommendations/rec.aspx?rec=13625).” 2021 edition.
12. ITU-T. “[P.863: Perceptual Objective Listening Quality Prediction](https://www.itu.int/ITU-T/recommendations/rec.aspx?rec=13570).” 2018 edition.
13. ITU-T. “[G.107: The E-model](https://www.itu.int/ITU-T/recommendations/rec.aspx?rec=12505).” 2015 edition.
14. W3C. “[Identifiers for WebRTC's Statistics API](https://www.w3.org/TR/webrtc-stats/).” 2025.
15. LiveKit. “[End-of-Turn Benchmark](https://github.com/livekit/eot-bench).” 2026.
16. Intron Innovation. “[AfriSwitch Dataset Card](https://huggingface.co/datasets/intronhealth/AfriSwitch).” 2026.
17. Koenecke et al. “[Racial Disparities in Automated Speech Recognition](https://doi.org/10.1073/pnas.1915768117).” PNAS, 2020.
18. NIST. “[AI Risk Management Framework: Measure](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/).” Accessed 2026.
19. AssemblyAI. “[Streaming Speech-to-Text Language Support](https://www.assemblyai.com/docs/faq/language-support-for-real-time-transcription).” Accessed 2026.
20. Intron. “[Sahara CodeSwitch Africa Challenge](https://www.intron.io/sahara-v2-5/sahara-codeswitch-africa/).” Accessed 2026.
21. Pipecat. “[YC Voice Agents Hackathon starter](https://github.com/pipecat-ai/yc-voice-agents-hackathon).” 2026.
22. Ogun. “[SBPN Multilingual Base model card](https://huggingface.co/ogunlao/SBPN_multilingual_base).” 2026.
23. Ray et al. “[$\tau$-Voice: Benchmarking Full-Duplex Voice Agents on Real-World Domains](https://arxiv.org/abs/2603.13686).” 2026.
