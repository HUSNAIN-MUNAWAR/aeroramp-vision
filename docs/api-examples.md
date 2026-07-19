# API examples

## Login

```bash
LOGIN=$(curl -s http://localhost:8000/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"admin@aeroramp.local","password":"AeroRamp-Dev-2026!"}')
TOKEN=$(printf '%s' "$LOGIN" | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
```

## Upload and process

```bash
curl -X POST http://localhost:8000/api/v1/videos/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F camera_id="$CAMERA_ID" \
  -F turnaround_id="$TURNAROUND_ID" \
  -F detector_backend=synthetic_color \
  -F run_now=false \
  -F file=@sample-data/synthetic-ramp.mp4

curl -X POST http://localhost:8000/api/v1/processing-jobs/$JOB_ID/run \
  -H "Authorization: Bearer $TOKEN"
```

## Review and incident

```bash
curl -X PATCH http://localhost:8000/api/v1/alerts/$ALERT_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"status":"confirmed","notes":"Reviewed against synchronized evidence"}'

curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"alert_id":"'$ALERT_ID'","title":"Ramp-safety investigation"}'
```

## Edge synchronization

```bash
curl -X POST http://localhost:8000/api/v1/edge-nodes/sync \
  -H 'X-Edge-Key: edge-development-key' \
  -H 'content-type: application/json' \
  -d @edge-batch.json
```

All list endpoints are tenant scoped. Domain errors use HTTP status and a stable code where specialized handling is needed, such as `CAMERA_CALIBRATION_REQUIRED`.
