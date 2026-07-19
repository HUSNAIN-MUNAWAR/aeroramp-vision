from __future__ import annotations

import argparse
import json
from pathlib import Path

import psutil  # type: ignore[import-untyped]
from aeroramp.vision.pipeline import process_video

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--detector", default="motion")
    parser.add_argument("--fps", type=float, default=4.0)
    args = parser.parse_args()
    before = psutil.Process().memory_info().rss
    result = process_video(args.video, Path("storage/benchmarks") / args.video.stem, args.detector, {}, [], [], [], target_fps=args.fps)
    after = psutil.Process().memory_info().rss
    print(json.dumps({**result.metadata, "memory_rss_before": before, "memory_rss_after": after, "memory_delta": after - before}, indent=2))
