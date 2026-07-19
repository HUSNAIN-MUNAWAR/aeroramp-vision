# Deployment

## Local Docker Compose

```bash
cp .env.example .env
# Set a unique AERORAMP_JWT_SECRET and database password.
docker compose config
docker compose build
docker compose up -d
```

The default services are PostgreSQL, Redis, API, processing worker, Next.js web console, and a looping video simulator. API and worker share evidence storage. The default demonstration is CPU-only.

Set `AERORAMP_SEED_DEVELOPMENT_DATA=false` in a non-demo deployment. Do not expose seeded credentials or the development edge key.

## Optional GPU profile

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build worker
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

The GPU override installs the optional YOLO dependencies and requests an NVIDIA device. CUDA driver, container runtime, compatible PyTorch build, model artifact, and site validation remain deployment responsibilities.

## Production topology

Use managed PostgreSQL, S3-compatible storage, TLS termination, centralized rate limiting, secrets management, worker autoscaling, read-only container filesystems where practical, backup/restore tests, evidence-capacity monitoring, and separated edge/camera networks. Run Alembic migrations as a controlled release step rather than from every replica.

## Health and observability

- `/health/live`: process liveness
- `/health/ready`: database readiness
- `/metrics`: Prometheus request counts and latency
- processing jobs: measured frame progress, FPS and errors
- edge nodes: last sync, status, queue/disk telemetry supplied by the node

Centralize JSON logs and correlate request, job, camera, turnaround, model, and edge identifiers.
