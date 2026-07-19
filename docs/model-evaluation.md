# Model and event evaluation

No production accuracy score is bundled. Site-specific labeled video is required. The repository provides runtime benchmarking, detector evaluation wrappers, and typed-event timing evaluation.

## Detection and tracking

Recommended detector metrics are per-class precision, recall, AP50, mAP50-95, small-object recall, and calibration of confidence thresholds. Tracking evaluation should include MOTA/HOTA where suitable, ID switches, fragmentation, time-to-recover after occlusion, track continuity, and class stability.

## Events and milestones

`scripts/evaluate_events.py` performs deterministic one-to-one matching by event type and timestamp tolerance. It reports true/false positives, false negatives, precision, recall, F1, mean absolute timing error, per-type metrics, matches, and unmatched indices.

```bash
python scripts/evaluate_events.py predictions.json ground-truth.json \
  --tolerance-seconds 2.0 \
  --output evaluation/event-metrics.json
```

Expected event shape:

```json
{"event_type":"aircraft_on_block","timestamp_seconds":42.3,"confidence":0.86}
```

## Runtime benchmark

```bash
python scripts/benchmark.py sample-data/synthetic-ramp.mp4 \
  --detector synthetic_color \
  --fps 6
```

The benchmark reports video dimensions, sampled frames, wall-clock throughput, source duration, observation hash, RSS before/after, and detector backend. Fixture throughput is useful for regression detection only; it is not representative of a trained neural detector.

## Acceptance gates

Define per-rule and per-camera gates before deployment: minimum recall for high-risk candidates, maximum alert burden, timing tolerance, availability, latency, and a documented human-review process. Re-evaluate after model, camera, zone, lighting, or stand-layout changes.
