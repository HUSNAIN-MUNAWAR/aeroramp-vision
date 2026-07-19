# Production readiness checklist

AeroRamp Vision is an engineering reference and evaluation platform, not a certified aviation safety product.

Before any operational deployment:

1. Validate each camera, stand, zone, class, rule, and milestone against representative site footage.
2. Measure per-camera and per-rule precision, recall, alert burden, timing error, latency, and availability.
3. Calibrate every metric rule and record survey method, reprojection error, and validation evidence.
4. Complete privacy, labor, data-protection, legal, cybersecurity, and model-license review.
5. Define who owns alert acknowledgment, incident escalation, false-positive correction, and evidence preservation.
6. Perform edge-node, RTSP, upload, model-file, API, browser, storage, and supply-chain threat modeling.
7. Test camera loss, database/queue loss, disk exhaustion, corrupt video, model timeout, network partition, retry, deduplication, backup, restore, and rollback.
8. Establish evidence access, chain-of-custody, legal hold, export, deletion, and audit procedures.
9. Load test expected cameras, inference FPS, upload size, concurrent review, and report volume.
10. Obtain airport-specific and relevant aviation-authority approval.

Do not enable automatic operational control, disciplinary action, pushback authorization, or departure authorization from computer-vision output.
