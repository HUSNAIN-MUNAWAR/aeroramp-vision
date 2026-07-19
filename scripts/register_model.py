from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx


def register(args: argparse.Namespace) -> dict[str, Any]:
    checkpoint = args.checkpoint.resolve()
    if not checkpoint.exists():
        raise FileNotFoundError(checkpoint)
    if checkpoint.suffix.lower() not in {".onnx", ".safetensors"}:
        raise ValueError("Registration CLI accepts ONNX or safetensors files only")
    login = httpx.post(
        f"{args.api_url.rstrip('/')}/api/v1/auth/login",
        json={"email": args.email, "password": args.password},
        timeout=30,
    )
    login.raise_for_status()
    token = login.json()["access_token"]
    payload = {
        "name": args.name,
        "version": args.version,
        "framework": args.framework,
        "input_resolution": args.input_resolution,
        "class_list": [value.strip() for value in args.classes.split(",") if value.strip()],
        "checkpoint_path": str(checkpoint),
        "checkpoint_checksum": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "validation_metrics": json.loads(args.validation_metrics),
        "safe_serialization": True,
    }
    response = httpx.post(
        f"{args.api_url.rstrip('/')}/api/v1/models",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register a validated deployment model")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--framework", default="ONNX Runtime")
    parser.add_argument("--input-resolution", default="960x960")
    parser.add_argument("--classes", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--validation-metrics", default="{}")
    arguments = parser.parse_args()
    print(json.dumps(register(arguments), indent=2, sort_keys=True))
