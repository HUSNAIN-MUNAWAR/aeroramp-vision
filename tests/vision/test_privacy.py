import numpy as np
from aeroramp.vision.privacy import apply_privacy
from aeroramp.vision.types import TrackPoint, TrackState


def test_privacy_zone_and_person_anonymization_modify_only_target_regions() -> None:
    rng = np.random.default_rng(2026)
    frame = rng.integers(0, 256, size=(120, 180, 3), dtype=np.uint8)
    track = TrackState(
        1,
        "person",
        [TrackPoint(0.0, (100, 35, 145, 100), (122.5, 67.5), 0.9)],
    )
    zones = [
        {
            "zone_type": "privacy_mask",
            "polygon": [[10, 10], [70, 10], [70, 80], [10, 80]],
        }
    ]
    output, applied = apply_privacy(frame, [track], zones, anonymize_persons=True)
    assert applied is True
    assert not np.array_equal(output[30:60, 20:60], frame[30:60, 20:60])
    assert not np.array_equal(output[45:80, 110:135], frame[45:80, 110:135])
    assert np.array_equal(output[100:115, 155:175], frame[100:115, 155:175])
