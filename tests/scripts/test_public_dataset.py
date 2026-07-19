from __future__ import annotations

import json

from scripts.download_public_dataset import DATASET_TITLE, transcode_clip, write_manifest
from scripts.generate_synthetic_video import generate


def test_transcode_public_dataset_helper_from_local_video(tmp_path):
    source = tmp_path / "source.mp4"
    output = tmp_path / "clip.mp4"
    manifest = tmp_path / "clip.json"
    generate(source, seconds=2, fps=12, width=320, height=180)

    metrics = transcode_clip(source, output, start_second=0, seconds=1, fps=6, width=160)
    write_manifest(manifest, output, str(source), metrics)

    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert output.exists()
    assert metrics["output_frames"] == 6
    assert metrics["output_width"] == 160
    assert data["dataset_title"] == DATASET_TITLE
    assert data["metrics"]["output_sha256"] == metrics["output_sha256"]
