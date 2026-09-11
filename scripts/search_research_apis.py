"""Search research APIs for biochar/anaerobic-digestion sources.

Examples:
    python scripts/search_research_apis.py "biochar anaerobic digestion methane"
    python scripts/search_research_apis.py "continuous anaerobic digestion biochar" --limit 10 --output outputs/api_search.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from biochar_ad_kinetics.research_apis import record_to_dict, search_all


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum records requested per API source",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Include provider-native payloads",
    )
    args = parser.parse_args()

    records = search_all(args.query, limit_per_source=args.limit)
    payload = [record_to_dict(record, include_raw=args.include_raw) for record in records]
    text = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {len(payload)} unique records to {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
