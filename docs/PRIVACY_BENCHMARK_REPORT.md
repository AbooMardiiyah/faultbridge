# PII Redaction Benchmark

## Scope and Method

This scorecard tests the privacy gate that runs before complaint analysis,
persistence, tool calls, and model-visible traces. A deterministic generator
creates 100 synthetic telco utterances, balanced at 25 each for Hausa-English,
Igbo-English, Pidgin-English, and Yoruba-English. No real customer data is used.

Ninety cases contain PII and ten are hard-negative operational utterances. The
positive set has 100 independently annotated spans: 25 Nigerian phone numbers, 25
email addresses, 25 account or SIM identifiers, and 25 long numeric identifiers.
Ten utterances contain two different PII types. Formats vary across compact,
spaced, hyphenated, local, and `+234` representations. The frozen generated case
file has SHA-256
`6ac7ada24eff73d0a817b1393bc7c90cf25f96fed90ebcf1b0667c497c719091`.

The scorer requires an exact match of PII type, start offset, and exclusive end
offset. It reports micro precision, recall, F1, exact-case failures, false-positive
and false-negative cases, and a hard leakage count after replacement. Labels are
created from explicit annotation markers in the generator rather than by calling
the production detector.

## Results

| Type | Expected | Predicted | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Phone | 25 | 25 | 100% | 100% | 100% |
| Email | 25 | 25 | 100% | 100% | 100% |
| Account/SIM identifier | 25 | 25 | 100% | 100% | 100% |
| Numeric identifier | 25 | 25 | 100% | 100% | 100% |
| **Overall** | **100** | **100** | **100%** | **100%** | **100%** |

All 100 cases matched exactly. False-positive case rate, false-negative case rate,
and post-redaction leakage rate were all 0%. The account matcher preserves labels
such as `SIM serial` and replaces only the identifier value, keeping the safe
transcript understandable.

## Reproduction and Limits

Run the complete scorecard without any API or model download:

```bash
make benchmark-privacy-prepare
make benchmark-privacy-score
```

The generated labelled utterances remain ignored because they intentionally
contain identifier-shaped strings. The generator and aggregate result are
committed, so the input hash and scores reproduce deterministically.

This result establishes the listed deterministic patterns; it is not a claim of
universal PII recognition. Unlabelled personal names, street addresses, and digit
sequences transcribed entirely as words are outside this version's scope. Caller
IDs are separately HMAC-pseudonymized before storage, and downstream traces are
also checked for forbidden source values in the executable agent scorecard.
