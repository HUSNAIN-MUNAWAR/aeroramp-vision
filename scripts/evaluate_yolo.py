from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    try:
        from ultralytics import YOLO  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Install the optional evaluation dependencies with pip install -e '.[yolo]'") from exc
    if not args.checkpoint.exists():
        raise FileNotFoundError(args.checkpoint)
    if not args.data.exists():
        raise FileNotFoundError(args.data)
    result = YOLO(str(args.checkpoint)).val(
        data=str(args.data),
        split=args.split,
        imgsz=args.imgsz,
        device=args.device,
        project=str(args.project),
        name=args.name,
        plots=True,
    )
    raw_metrics = getattr(result, "results_dict", {})
    metrics = {
        str(key): float(value)
        for key, value in raw_metrics.items()
        if isinstance(value, int | float)
    }
    return {
        "checkpoint": str(args.checkpoint),
        "dataset": str(args.data),
        "split": args.split,
        "metrics": metrics,
        "save_dir": str(getattr(result, "save_dir", args.project / args.name)),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate a trained airport detector")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", choices=["val", "test"], default="test")
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--project", type=Path, default=Path("runs/aeroramp"))
    parser.add_argument("--name", default="evaluation")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    payload = evaluate(arguments)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered + "\n")
    print(rendered)
