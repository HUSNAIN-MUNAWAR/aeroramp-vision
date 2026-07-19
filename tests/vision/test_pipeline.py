from pathlib import Path

from aeroramp.vision.milestones import MilestoneRule
from aeroramp.vision.pipeline import probe_video, process_video
from aeroramp.vision.rules import RuleConfig

from scripts.generate_synthetic_video import generate


def test_real_video_pipeline(tmp_path: Path) -> None:
    video = tmp_path / "fixture.mp4"
    generate(video, seconds=8)
    metadata = probe_video(video)
    assert metadata["frame_count"] > 0
    zones = [
        {"id": "envelope", "name": "Aircraft envelope", "zone_type": "aircraft_safety_envelope", "polygon": [[170, 90], [540, 90], [540, 290], [170, 290]]},
        {"id": "pushback", "name": "Pushback route", "zone_type": "pushback_path", "polygon": [[40, 210], [610, 210], [610, 330], [40, 330]]},
    ]
    rules = [
        RuleConfig("person-rule", "person_in_restricted_zone", "high", "envelope", zones[0]["polygon"], {"classes": ["person"]}, 0.5, 5),
        RuleConfig("pushback-rule", "pushback_path_obstruction", "high", "pushback", zones[1]["polygon"], {"classes": ["service_vehicle"]}, 0.5, 5),
    ]
    milestones = [MilestoneRule("aircraft_on_block", "aircraft", zones[0]["polygon"], 1.0)]
    result = process_video(video, tmp_path / "out", "synthetic_color", {}, zones, rules, milestones, target_fps=6)
    assert len(result.tracks) >= 3
    assert any(track.class_name == "aircraft" for track in result.tracks)
    assert any(alert.rule_type == "person_in_restricted_zone" for alert in result.alerts)
    assert any(m.milestone_type == "aircraft_on_block" for m in result.milestones)
    assert Path(result.observation_path).exists()
    assert Path(result.annotated_video_path or "").exists()
    assert result.evidence_clips
    assert all(Path(path).exists() for path in result.evidence_clips.values())
    assert result.metadata["processing_fps"] > 0
