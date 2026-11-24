import numpy as np
import pytest

from aeroramp.vision.pipeline import _write_snapshot


def test_snapshot_write_failure_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr("aeroramp.vision.pipeline.cv2.imwrite", lambda *_args: False)
    with pytest.raises(RuntimeError, match="Could not write evidence snapshot"):
        _write_snapshot(tmp_path / "alert.jpg", np.zeros((8, 8, 3), dtype=np.uint8))
