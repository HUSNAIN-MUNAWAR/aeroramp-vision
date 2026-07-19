from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2

DATASET_TITLE = "Aerospace Ground Equipment ensures aircraft are ready for flight"
PUBLISHER = "DVIDS / U.S. Air Force"
SOURCE_PAGE = (
    "https://www.dvidshub.net/video/838428/"
    "aerospace-ground-equipment-ensures-aircraft-ready-flight"
)
COPYRIGHT_PAGE = "https://www.dvidshub.net/about/copyright"
HLS_SOURCE = (
    "https://d34w7g4gy10iej.cloudfront.net/video/2204/DOD_108909050/"
    "DOD_108909050-768x432-1200k-hls_8.m3u8"
)
FULL_MP4_SOURCE = (
    "https://d34w7g4gy10iej.cloudfront.net/video/2204/DOD_108909050/"
    "DOD_108909050.mp4"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_capture(source: str | Path) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(
            "Could not open the DVIDS media stream. Try --source-url with the full MP4 "
            f"fallback documented in {Path('docs/DATASET.md')}."
        )
    return capture


def transcode_clip(
    source: str | Path,
    output: Path,
    *,
    start_second: float,
    seconds: float,
    fps: float,
    width: int,
) -> dict[str, Any]:
    capture = _open_capture(source)
    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if source_fps <= 0 or source_width <= 0 or source_height <= 0:
        capture.release()
        raise RuntimeError("DVIDS video metadata is incomplete or invalid.")

    output.parent.mkdir(parents=True, exist_ok=True)
    height = max(2, int(round(width * source_height / source_width)))
    if height % 2:
        height += 1
    writer = cv2.VideoWriter(
        str(output),
        cv2.VideoWriter_fourcc(*"mp4v"),  # type: ignore[attr-defined]
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"Could not create output video writer for {output}.")

    capture.set(cv2.CAP_PROP_POS_MSEC, start_second * 1000.0)
    sample_every = max(1, round(source_fps / fps))
    frames_read = 0
    frames_written = 0
    max_read_frames = int(seconds * source_fps) + sample_every
    while frames_read <= max_read_frames:
        ok, frame = capture.read()
        if not ok:
            break
        if frames_read % sample_every == 0:
            resized = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            writer.write(resized)
            frames_written += 1
        frames_read += 1
        if frames_written >= int(seconds * fps):
            break

    capture.release()
    writer.release()
    if frames_written == 0:
        output.unlink(missing_ok=True)
        raise RuntimeError("No frames were written from the selected DVIDS clip window.")

    return {
        "source_fps": source_fps,
        "source_width": source_width,
        "source_height": source_height,
        "source_frame_count": frame_count,
        "start_second": start_second,
        "requested_seconds": seconds,
        "output_width": width,
        "output_height": height,
        "output_fps": fps,
        "output_frames": frames_written,
        "output_seconds": frames_written / fps,
        "output_sha256": sha256_file(output),
    }


def write_manifest(path: Path, output_video: Path, source_url: str, metrics: dict[str, Any]) -> None:
    manifest = {
        "dataset_title": DATASET_TITLE,
        "publisher": PUBLISHER,
        "source_page": SOURCE_PAGE,
        "source_url": source_url,
        "copyright_page": COPYRIGHT_PAGE,
        "license": "Public domain / U.S. Government visual information, with DVIDS public-use restrictions",
        "non_endorsement": (
            "The appearance of U.S. Department of Defense visual information does not imply "
            "or constitute DoD endorsement."
        ),
        "prepared_at": datetime.now(UTC).isoformat(),
        "output_video": str(output_video.as_posix()),
        "transformations": [
            "Selected a short public-demo window from the official DVIDS video stream.",
            "Resampled to a CPU-friendly frame rate.",
            "Resized to a small local-development resolution.",
            "No labels or detections were manually authored.",
        ],
        "metrics": metrics,
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare the DVIDS public-domain AGE ramp-operations demo clip."
    )
    parser.add_argument("--output", type=Path, default=Path("sample-data/dvids-age-public.mp4"))
    parser.add_argument("--manifest", type=Path, default=Path("sample-data/dvids-age-public.json"))
    parser.add_argument("--source-url", default=HLS_SOURCE)
    parser.add_argument("--start-second", type=float, default=8.0)
    parser.add_argument("--seconds", type=float, default=36.0)
    parser.add_argument("--fps", type=float, default=12.0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists() and args.manifest.exists() and not args.force:
        print(f"Using existing demo clip: {args.output}")
        print(f"Manifest: {args.manifest}")
        return
    print(f"Source: {DATASET_TITLE}")
    print(f"Publisher: {PUBLISHER}")
    print(f"Official page: {SOURCE_PAGE}")
    print(f"Copyright and public-use restrictions: {COPYRIGHT_PAGE}")
    metrics = transcode_clip(
        args.source_url,
        args.output,
        start_second=args.start_second,
        seconds=args.seconds,
        fps=args.fps,
        width=args.width,
    )
    write_manifest(args.manifest, args.output, args.source_url, metrics)
    print(f"Wrote {args.output} ({args.output.stat().st_size} bytes)")
    print(f"Wrote {args.manifest}")
    print(f"Frames: {metrics['output_frames']} at {metrics['output_fps']} fps")
    print(f"SHA256: {metrics['output_sha256']}")


if __name__ == "__main__":
    main()
