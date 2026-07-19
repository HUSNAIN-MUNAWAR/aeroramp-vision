# Privacy and retention

AeroRamp Vision uses anonymous track IDs within a camera/job session. It does not implement face recognition, biometric identity, worker ranking, or passenger identity.

## Controls in the reference implementation

- camera privacy-mask and masked-region fields
- frame-level polygon blurring for configured privacy zones
- optional full-person-box anonymization for detectors that emit the generic `person` class
- redaction metadata attached to generated evidence assets
- role- and tenant-protected evidence endpoints
- encrypted stream URL storage
- evidence metadata and hashes
- audit records for review and administrative actions
- configurable camera retention settings
- explicit retention cleanup command with dry-run behavior

```bash
python scripts/retention_cleanup.py --dry-run
python scripts/retention_cleanup.py --apply
```

Audit records are not silently removed. Production deployments should define separate retention for raw video, annotated video, snapshots, clips, observations, tracks, alerts, incidents, reports, and audits. Legal holds and incident preservation must override routine cleanup.

The executable pipeline can blur configured privacy polygons and, when enabled, full detected-person boxes before snapshots, clips, and annotated video are written. It does not identify people and does not include a dedicated face detector. These controls are a privacy baseline, not a production-grade guarantee: deployments must validate detector misses, occlusion, reflections, exports, and every storage path, and should apply redaction at the edge whenever policy requires it.
