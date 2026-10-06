"""Save fixed-horizon predictions, then score the separately collected endpoints."""

import argparse
import json
from pathlib import Path

from biochar_ad_kinetics.prospective_forecast import evaluate, predict, write_new

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prediction = commands.add_parser("predict", help="Read prefix only and save predictions")
    prediction.add_argument("--prefix", type=Path, required=True)
    prediction.add_argument("--cohort", type=Path, required=True)
    prediction.add_argument(
        "--protocol", type=Path, default=ROOT / "data/validation/future_batch_forecast_v1.json"
    )
    prediction.add_argument("--output", type=Path, required=True)
    scoring = commands.add_parser("evaluate", help="Score saved predictions; no model refit")
    scoring.add_argument("--predictions", type=Path, required=True)
    scoring.add_argument("--prefix", type=Path, required=True)
    scoring.add_argument("--endpoints", type=Path, required=True)
    scoring.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "predict":
        result = predict(
            args.prefix, json.loads(args.cohort.read_text()), json.loads(args.protocol.read_text())
        )
    else:
        result = evaluate(json.loads(args.predictions.read_text()), args.prefix, args.endpoints)
    write_new(args.output, result)
    print(f"Saved {args.command} artifact: {args.output}")


if __name__ == "__main__":
    main()
