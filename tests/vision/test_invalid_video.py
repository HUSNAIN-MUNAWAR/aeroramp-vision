from pathlib import Path

import pytest
from aeroramp.vision.pipeline import probe_video


def test_corrupt_video(tmp_path: Path) -> None:
    path = tmp_path / "bad.mp4"
    path.write_bytes(b"not-a-video")
    with pytest.raises(ValueError, match="cannot be decoded"):
        probe_video(path)
