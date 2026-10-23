"""Review unknown intent clusters offline. Does not upload, store or echo messages.

Usage:
    python scripts/review_intents.py --demo
    python scripts/review_intents.py --consented-input curated.json --acknowledge-consent
The JSON file must contain a list of short, explicitly consented examples.
NEVER pass production logs or exported conversation history here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentinel.discovery import discover_unknown_topics

_DEMO = [
    "تنظیم webhook اختصاصی چه طور است",
    "وبهوک اختصاصی کجا تنظیم می‌شود",
    "می‌خواهم صف کار پس زمینه داشته باشم",
    "صف کار پس زمینه قابل تنظیم است",
    "صف پردازش وظایف عقب افتاده",
    "اتصال rpc در محیط sandbox",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true", help="Use synthetic built-in prompts")
    group.add_argument("--consented-input", type=Path,
                       help="A JSON array of explicitly consented, pre-reviewed prompts")
    parser.add_argument("--acknowledge-consent", action="store_true",
                        help="I have consent for ALL samples; none contains real credentials")
    args = parser.parse_args()
    if args.demo:
        prompts = _DEMO
    else:
        if not args.acknowledge_consent:
            parser.error("Explicit sample consent is required; never upload raw user messages.")
        if args.consented_input.stat().st_size > 250_000:
            parser.error("Sample file is too large for offline review.")
        prompts = json.loads(args.consented_input.read_text(encoding="utf-8"))
        if not isinstance(prompts, list) or not all(isinstance(x, str) for x in prompts):
            parser.error("Input must be a JSON list of strings.")
    output = discover_unknown_topics(prompts)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
