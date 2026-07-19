from __future__ import annotations

import os
import time
from pathlib import Path

import cv2
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

VIDEO_PATH = Path(os.getenv("AERORAMP_SIMULATOR_VIDEO", "sample-data/synthetic-ramp.mp4"))
app = FastAPI(title="AeroRamp Local Stream Simulator")


def frames():
    while True:
        capture = cv2.VideoCapture(str(VIDEO_PATH))
        if not capture.isOpened():
            raise RuntimeError(f"Simulator video unavailable: {VIDEO_PATH}")
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 12)
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            ok, encoded = cv2.imencode(".jpg", frame)
            if ok:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"
            time.sleep(1 / fps)
        capture.release()


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ready" if VIDEO_PATH.exists() else "not_ready", "video": str(VIDEO_PATH), "simulated": True}


@app.get("/stream.mjpg")
def stream() -> StreamingResponse:
    if not VIDEO_PATH.exists():
        raise HTTPException(status_code=404, detail="Run scripts/generate_synthetic_video.py first")
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")
