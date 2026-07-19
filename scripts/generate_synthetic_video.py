from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def generate(path: Path, seconds: int = 12, fps: int = 12, width: int = 640, height: int = 360) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Could not create video writer")
    total = seconds * fps
    for index in range(total):
        frame: np.ndarray = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (20, 24, 28)
        cv2.rectangle(frame, (80, 80), (560, 290), (55, 55, 55), 2)
        cv2.putText(frame, "SYNTHETIC TEST FIXTURE", (18, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 2)
        # Blue aircraft moves to the stand, then remains stationary.
        aircraft_x = min(260, 30 + index * 3)
        cv2.rectangle(frame, (aircraft_x, 150), (aircraft_x + 150, 205), (255, 0, 0), -1)
        cv2.circle(frame, (aircraft_x + 120, 178), 22, (255, 0, 0), -1)
        # Yellow service vehicle crosses the restricted zone.
        vehicle_x = 610 - index * 4
        if vehicle_x > -80:
            cv2.rectangle(frame, (vehicle_x, 235), (vehicle_x + 75, 275), (0, 255, 255), -1)
        # Red anonymous person enters the stand envelope for several seconds.
        if 35 <= index <= 105:
            person_x = 130 + (index - 35) * 2
            cv2.rectangle(frame, (person_x, 105), (person_x + 18, 150), (0, 0, 255), -1)
        writer.write(frame)
    writer.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("sample-data/synthetic-ramp.mp4"))
    parser.add_argument("--seconds", type=int, default=12)
    args = parser.parse_args()
    generate(args.output, seconds=args.seconds)
    print(args.output)
