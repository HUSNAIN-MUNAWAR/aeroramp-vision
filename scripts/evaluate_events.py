from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aeroramp.evaluation import evaluate_timed_events


def load_events(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        data = data.get("events") or data.get("milestones") or data.get("alerts")
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{path} must contain a JSON array of event objects")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate typed event timestamps")
    parser.add_argument("predictions", type=Path)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("--tolerance-seconds", type=float, default=2.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    metrics = evaluate_timed_events(
        load_events(args.predictions),
        load_events(args.ground_truth),
        tolerance_seconds=args.tolerance_seconds,
    )
    rendered = json.dumps(metrics, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    print(rendered)
