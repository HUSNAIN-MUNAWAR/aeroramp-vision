from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import cv2
from aeroramp.vision.pipeline import probe_video, process_video

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sample-data/dvids-age-public.mp4"
OUTPUT_DIR = ROOT / "docs/runtime_evidence"
ANNOTATED = OUTPUT_DIR / "aeroramp-dvids-motion-runtime.mp4"
POSTER = OUTPUT_DIR / "aeroramp-dvids-motion-runtime-poster.jpg"
TRACE = OUTPUT_DIR / "aeroramp-dvids-motion-track-trace.csv"
OBSERVATIONS = OUTPUT_DIR / "aeroramp-dvids-motion-observations.json.gz"
SUMMARY = OUTPUT_DIR / "aeroramp-dvids-motion-runtime-summary.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path) -> dict[str, str | int]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def capture_poster(video: Path) -> dict[str, int | float]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Annotated output cannot be decoded: {video}")
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, frames // 2))
    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        raise RuntimeError("Could not read a poster frame from annotated output")
    cv2.imwrite(str(POSTER), frame)
    return {"frames": frames, "fps": fps, "width": width, "height": height}


def main() -> None:
    os.chdir(ROOT)
    if not SOURCE.exists():
        raise SystemExit(
            "Missing sample-data/dvids-age-public.mp4; run scripts/download_public_dataset.py"
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (ANNOTATED, POSTER, TRACE, OBSERVATIONS, SUMMARY):
        path.unlink(missing_ok=True)

    run_dir = OUTPUT_DIR / "_aeroramp_run"
    run_dir.mkdir(parents=True, exist_ok=True)
    result = process_video(
        SOURCE,
        run_dir,
        detector_backend="motion",
        detector_config={},
        zones=[],
        rules=[],
        milestone_rules=[],
        target_fps=4.0,
    )
    if result.annotated_video_path is None:
        raise RuntimeError("Motion runtime did not produce an annotated video")
    Path(result.annotated_video_path).replace(ANNOTATED)
    Path(result.observation_path).replace(OBSERVATIONS)
    run_dir.rmdir()

    with gzip.open(OBSERVATIONS, "rt", encoding="utf-8") as fh:
        observations = json.load(fh)
    rows: list[dict[str, object]] = []
    for observation in observations:
        for track in observation["tracks"]:
            bbox = track["bbox"]
            rows.append(
                {
                    "frame_index": observation["frame_index"],
                    "timestamp_seconds": observation["timestamp_seconds"],
                    "track_id": track["track_id"],
                    "class_name": track["class_name"],
                    "confidence": track["confidence"],
                    "bbox_x_min": bbox[0],
                    "bbox_y_min": bbox[1],
                    "bbox_x_max": bbox[2],
                    "bbox_y_max": bbox[3],
                }
            )
    if not rows:
        raise RuntimeError("Motion runtime produced no track rows")
    with TRACE.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    encoded = capture_poster(ANNOTATED)
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "os": platform.platform(),
            "python": sys.version.split()[0],
            "opencv": cv2.__version__,
        },
        "source": {
            "dataset": "DVIDS video 838428: Aerospace Ground Equipment ensures aircraft are ready for flight",
            "publisher": "DVIDS / U.S. Air Force",
            "source_page": "https://www.dvidshub.net/video/838428/aerospace-ground-equipment-ensures-aircraft-ready-flight",
            "license": "Public domain / U.S. Government visual information with DVIDS public-use restrictions",
            "file": SOURCE.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(SOURCE),
            "metadata": probe_video(SOURCE),
        },
        "detector": {
            "backend": "motion",
            "algorithm": "OpenCV MOG2 background subtraction, median blur, morphology, contour-area filtering",
            "class_output": "moving_object",
            "model_checkpoint": None,
        },
        "pipeline": {
            **result.metadata,
            "track_count": len(result.tracks),
            "observation_frames": len(observations),
            "track_trace_rows": len(rows),
            "alerts": len(result.alerts),
            "milestones": len(result.milestones),
            "encoded_output": encoded,
        },
        "artifacts": {
            "annotated_video": artifact(ANNOTATED),
            "poster": artifact(POSTER),
            "track_trace": artifact(TRACE),
            "observations": artifact(OBSERVATIONS),
        },
        "claim_boundary": [
            "This is a real OpenCV motion-detector run over decoded public DVIDS video pixels.",
            "The detector emits generic moving_object regions; it does not identify aircraft, vehicles, or people.",
            "No airport-specific checkpoint, training run, accuracy benchmark, certification, or manually authored detection is claimed.",
            "No safety rules were supplied to this standalone benchmark, so zero alerts is an intentional configuration result, not a safety conclusion.",
        ],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
