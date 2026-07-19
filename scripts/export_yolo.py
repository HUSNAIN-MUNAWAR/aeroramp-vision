from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def export(args: argparse.Namespace) -> dict[str, Any]:
    try:
        from ultralytics import YOLO  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Install the optional export dependencies with pip install -e '.[yolo]'") from exc
    if not args.checkpoint.exists():
        raise FileNotFoundError(args.checkpoint)
    exported = YOLO(str(args.checkpoint)).export(
        format=args.format,
        imgsz=args.imgsz,
        dynamic=args.dynamic,
        simplify=args.simplify,
        opset=args.opset,
        device=args.device,
    )
    exported_path = Path(str(exported)).resolve()
    if not exported_path.exists():
        raise RuntimeError(f"Model export did not produce the expected file: {exported_path}")
    return {
        "checkpoint": str(args.checkpoint.resolve()),
        "exported_path": str(exported_path),
        "format": args.format,
        "sha256": hashlib.sha256(exported_path.read_bytes()).hexdigest(),
        "size_bytes": exported_path.stat().st_size,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export a trained detector to a safer deployment format")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--format", choices=["onnx"], default="onnx")
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--dynamic", action="store_true")
    parser.add_argument("--simplify", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(export(arguments), indent=2, sort_keys=True))
