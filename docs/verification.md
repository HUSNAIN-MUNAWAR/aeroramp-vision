# Delivery verification

This file records the commands executed for the packaged delivery on 2026-07-19. It is not a claim about performance or correctness on other hardware, camera views, airport sites, or datasets.

## Toolchain used

- Python 3.13.5 (the project targets Python 3.12+)
- Node.js 22.16.0
- npm 10.9.2
- FFmpeg 7.1.3
- OpenCV 4.13.0

## Static analysis and automated tests

```bash
ruff check .
mypy apps/api/aeroramp packages/sdk/python/aeroramp_sdk scripts
pytest
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
npm --prefix apps/web audit --audit-level=high
```

Observed results:

- Ruff: passed
- MyPy: passed for 40 source files
- Pytest: 17 passed
- Frontend lint/typecheck: passed
- Next.js production build: passed; 10 application routes generated
- npm audit: 0 vulnerabilities reported

The targeted workflow suite also passed:

```bash
pytest -vv \
  tests/integration/test_api_workflow.py \
  tests/integration/test_edge_sync.py \
  tests/integration/test_model_deployment.py
```

Observed result: 4 passed. This covers real MP4 upload/processing, tracks, alerts, milestones, protected evidence, incident/review actions, tenant isolation, edge authentication/deduplication, and model deployment rollback.

## Database verification

```bash
AERORAMP_DATABASE_URL=sqlite:////tmp/aeroramp-clean.db alembic upgrade head
AERORAMP_DATABASE_URL=sqlite:////tmp/aeroramp-clean.db alembic current
AERORAMP_DATABASE_URL=sqlite:////tmp/aeroramp-clean.db alembic check
```

Observed result: all four migrations applied through `ec07fad70414 (head)` and Alembic reported no new upgrade operations.

## Runtime verification

The FastAPI application was started against a clean seeded SQLite database. The following endpoints returned HTTP 200:

- `/health/ready`
- `/api/v1/auth/login`
- `/api/v1/dashboard`
- `/metrics`

## Measured fixture benchmark

```bash
PYTHONPATH=apps/api:. python scripts/generate_synthetic_video.py \
  --output /tmp/aeroramp-synthetic.mp4 --seconds 12
PYTHONPATH=apps/api:. python scripts/benchmark.py \
  /tmp/aeroramp-synthetic.mp4 --detector synthetic_color --fps 6
```

Observed values in this build environment:

- Source: 640x360, 12 FPS, 144 frames, 12 seconds
- Processed frames: 72
- Processing time: 0.609 seconds
- Measured pipeline rate: 118.3 processed frames/second
- Metric calibration: false
- Privacy masking: false for this benchmark fixture

The `synthetic_color` backend is a deterministic test-fixture detector. This benchmark is useful for regression and pipeline overhead checks; it is not an airport-model accuracy measurement and must not be compared with production YOLO/TensorRT performance.

## Docker status

`docker compose config` could not be executed because the delivery workspace did not contain the Docker CLI (`docker: command not found`, exit 127). The following files were parsed successfully with PyYAML:

- `docker-compose.yml` with `postgres`, `redis`, `api`, `worker`, `web`, and `simulator`
- `docker-compose.gpu.yml` with the optional GPU worker override
- `.github/workflows/ci.yml` with backend, frontend, and Docker jobs

The CI workflow is configured to run Compose validation and build both Dockerfiles on a Docker-enabled GitHub runner.

## Public Dataset Addendum

The public dataset integration was verified on 2026-07-19 with the DVIDS `Aerospace Ground Equipment ensures aircraft are ready for flight` demo clip documented in [docs/DATASET.md](DATASET.md).

```bash
py -3.12 scripts/download_public_dataset.py --force
py -3.12 scripts/download_public_dataset.py --help
py -3.12 scripts/benchmark.py sample-data/dvids-age-public.mp4 --detector motion --fps 6
py -3.12 -m ruff check .
py -3.12 -m mypy apps/api/aeroramp packages/sdk/python/aeroramp_sdk scripts
py -3.12 -m pytest
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web audit --audit-level=high
cd apps/web && npx next build --webpack
```

Observed public-demo results:

- Prepared clip: 640x360 MP4, 12 FPS, 432 frames, 36 seconds, SHA-256 `f01e0dc46143e263d40ab73e45312aa373fccd24a206db8e7f3f8961744a0da4`.
- API processing run: completed with `motion`, 216 sampled frames, 152 generic tracks, 135 review candidates, and 135 CSV report rows.
- Evidence check: authenticated snapshot and clip requests returned HTTP 200.
- Benchmark script: processed 216 sampled frames at 33.2 processed frames/second on this local CPU-only run.
- Screenshots: refreshed from the local Next.js app backed by the public-demo processing run.

Local Windows note: some Python commands were run through a small in-process `platform.machine` monkeypatch because SQLAlchemy import could stall inside Windows WMI discovery on this workstation. No repository runtime code depends on that workaround, and Linux CI does not require it.
