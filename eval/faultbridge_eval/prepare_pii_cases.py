from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MARKER = re.compile(r"\{\{?([a-z_]+):(.*?)\}\}?")
LANGUAGE_PAIRS = (
    "Hausa-English",
    "Igbo-English",
    "Pidgin-English",
    "Yoruba-English",
)


def render(marked_text: str) -> tuple[str, list[dict[str, int | str]]]:
    text_parts: list[str] = []
    spans: list[dict[str, int | str]] = []
    cursor = 0
    output_length = 0
    for match in MARKER.finditer(marked_text):
        prefix = marked_text[cursor : match.start()]
        value = match.group(2)
        text_parts.extend((prefix, value))
        output_length += len(prefix)
        spans.append(
            {
                "type": match.group(1),
                "start": output_length,
                "end": output_length + len(value),
            }
        )
        output_length += len(value)
        cursor = match.end()
    text_parts.append(marked_text[cursor:])
    return "".join(text_parts), spans


def marked_cases() -> list[tuple[str, str]]:
    phone_values = (
        "0803 123 4567",
        "+234-806-234-5678",
        "07051234567",
        "0909-876-5432",
        "234 813 246 8024",
    )
    phone_contexts = (
        "Lambar waya ta ce {{phone:{}}}, network din bai yi ba.",
        "Kpọọ m na {{phone:{}}}; network anaghị arụ ọrụ.",
        "Abeg call me for {{phone:{}}}, data no dey work.",
        "Nọ́mbà mi ni {{phone:{}}}, network kò ṣiṣẹ́.",
    )
    email_values = (
        "ada.okeke@example.com",
        "musa+support@sample.ng",
        "tunde_ade@demo.co.uk",
        "ngozi-1@test.africa",
        "billing.case@sub.example.org",
    )
    email_contexts = (
        "Aika amsa zuwa {{email:{}}} don Allah.",
        "Email m bụ {{email:{}}}; biko ziga update.",
        "Send the update give {{email:{}}} abeg.",
        "Fi ìmúdójúìwọ̀n ránṣẹ́ sí {{email:{}}}.",
    )
    account_values = (
        "FB-100234",
        "AB12345678",
        "SUB-778899",
        "ICC-12345678",
        "IMSI-44005566",
    )
    account_contexts = (
        "My account number {{account:{}}} has no data.",
        "Check acct no: {{account:{}}}, recharge no enter.",
        "Subscriber ID {{account:{}}} ka duba shi.",
        "My SIM serial is {{account:{}}} and service is down.",
    )
    numeric_values = (
        "1234 567 8901",
        "5399-1234-5678-9012",
        "22133445566",
        "987 654 321 09",
        "440055006677",
    )
    numeric_contexts = (
        "My NIN is {{numeric_identifier:{}}}; do not repeat it aloud.",
        "BVN dina shine {{numeric_identifier:{}}}, ka boye shi.",
        "Card number m bụ {{numeric_identifier:{}}}; biko kpuchie ya.",
        "The private identifier is {{numeric_identifier:{}}}, abeg mask am.",
    )
    cases = [
        (pair, context.format(value))
        for pair, context in zip(LANGUAGE_PAIRS, phone_contexts, strict=True)
        for value in phone_values
    ]
    cases += [
        (pair, context.format(value))
        for pair, context in zip(LANGUAGE_PAIRS, email_contexts, strict=True)
        for value in email_values
    ]
    cases += [
        (pair, context.format(value))
        for pair, context in zip(LANGUAGE_PAIRS, account_contexts, strict=True)
        for value in account_values
    ]
    cases += [
        (pair, context.format(value))
        for pair, context in zip(LANGUAGE_PAIRS, numeric_contexts, strict=True)
        for value in numeric_values
    ]
    cases += [
        (
            "Hausa-English",
            "Call {{phone:0803 000 0001}} or mail {{email:case1@example.com}}.",
        ),
        (
            "Hausa-English",
            "Use account number {{account:FB-MULTI01}} and NIN {{numeric_identifier:1000 200 3004}}.",
        ),
        (
            "Igbo-English",
            "Kpọọ {{phone:+234 806 000 0002}}; acct no {{account:IG-MULTI02}}.",
        ),
        (
            "Igbo-English",
            "Email {{email:case3@example.ng}} with ID {{numeric_identifier:2000-3000-4005}}.",
        ),
        (
            "Pidgin-English",
            "Abeg mask {{phone:07050000003}} and {{email:case4@example.org}}.",
        ),
        (
            "Pidgin-English",
            "Subscriber ID {{account:PD-MULTI04}} uses card {{numeric_identifier:5000 6000 7000 8006}}.",
        ),
        (
            "Yoruba-English",
            "Nọ́mbà {{phone:09090000004}}; email {{email:case5@example.africa}}.",
        ),
        (
            "Yoruba-English",
            "SIM serial {{account:YO-MULTI05}} and NIN {{numeric_identifier:3000 400 5007}}.",
        ),
        (
            "Pidgin-English",
            "Reach {{email:case6@sub.example.com}} or {{phone:234-813-000-0005}}.",
        ),
        (
            "Hausa-English",
            "Customer ID {{account:CS-MULTI06}}; private ID {{numeric_identifier:440055006688}}.",
        ),
    ]
    return cases


NEGATIVE_CASES = (
    ("Hausa-English", "I bought a 5 GB bundle for 1500 naira yesterday."),
    ("Igbo-English", "The ticket is FB-2026-09 and the cell is LOS-IKJ-04."),
    (
        "Pidgin-English",
        "Call quality dropped around 08:30, then recovered at 09:15.",
    ),
    ("Yoruba-English", "My balance moved from 2500 to 1200 without explanation."),
    ("Hausa-English", "The router address is 192.168.1.1 and the light is red."),
    ("Igbo-English", "Use *312# to check the bundle; no private detail is included."),
    ("Pidgin-English", "There were 12 failed calls during the last 48 hours."),
    ("Yoruba-English", "Network generation 5G appears, but data still no dey move."),
    ("Yoruba-English", "The incident date is 2026-09-13 and restoration says 14:00."),
    (
        "Igbo-English",
        "Please transfer me to customer care; I will share details securely.",
    ),
)


def build_cases() -> list[dict[str, object]]:
    cases = []
    for index, (language_pair, marked) in enumerate(
        (*marked_cases(), *NEGATIVE_CASES), start=1
    ):
        text, spans = render(marked)
        cases.append(
            {
                "case_id": f"pii-{index:03d}",
                "language_pair": language_pair,
                "text": text,
                "expected_spans": spans,
                "synthetic": True,
            }
        )
    return cases


def run(output: Path) -> None:
    cases = build_cases()
    if len(cases) != 100:
        raise ValueError(f"expected 100 cases, built {len(cases)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases),
        encoding="utf-8",
    )
    print(f"Wrote {len(cases)} synthetic cases to {output}")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Build the frozen PII scorecard")
    command.add_argument(
        "--output", type=Path, default=Path("benchmark/pii_cases.jsonl")
    )
    return command


if __name__ == "__main__":
    run(parser().parse_args().output)
