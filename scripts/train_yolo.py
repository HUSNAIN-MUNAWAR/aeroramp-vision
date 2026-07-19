from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def train(args: argparse.Namespace) -> dict[str, Any]:
    try:
        from ultralytics import YOLO  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Install the optional training dependencies with pip install -e '.[yolo]'") from exc
    if not args.data.exists():
        raise FileNotFoundError(args.data)
    model = YOLO(args.model)
    result = model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        seed=args.seed,
        device=args.device,
        workers=args.workers,
        project=str(args.project),
        name=args.name,
        exist_ok=args.exist_ok,
        deterministic=True,
    )
    save_dir = str(getattr(result, "save_dir", args.project / args.name))
    return {
        "save_dir": save_dir,
        "base_model": args.model,
        "dataset": str(args.data),
        "epochs": args.epochs,
        "image_size": args.imgsz,
        "seed": args.seed,
        "device": args.device,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train an airport-specific Ultralytics detector")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--project", type=Path, default=Path("runs/aeroramp"))
    parser.add_argument("--name", default="detector")
    parser.add_argument("--exist-ok", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(train(arguments), indent=2))
