from __future__ import annotations

import hashlib
import re
from pathlib import Path

from aeroramp.core.config import get_settings
from cryptography.fernet import Fernet

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi"}


def safe_filename(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name).name).strip(".-")
    if not clean:
        raise ValueError("Invalid filename")
    return clean[:180]


def validate_video_name(name: str) -> str:
    clean = safe_filename(name)
    if Path(clean).suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError("Unsupported video type. Supported extensions: mp4, mov, avi")
    return clean


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fernet() -> Fernet:
    settings = get_settings()
    key = hashlib.sha256(settings.jwt_secret.encode()).digest()
    import base64

    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
