.PHONY: install seed fixture api worker web test lint typecheck build migrate benchmark compose-up compose-down clean

install:
	pip install -e '.[dev]'
	cd apps/web && npm install

seed:
	python scripts/seed.py

fixture:
	python scripts/generate_synthetic_video.py

api:
	uvicorn aeroramp.main:app --app-dir apps/api --reload

worker:
	python apps/worker/main.py

web:
	cd apps/web && npm run dev

test:
	pytest

lint:
	ruff check .

typecheck:
	mypy apps/api/aeroramp packages/sdk/python/aeroramp_sdk scripts
	cd apps/web && npm run typecheck

build:
	cd apps/web && npm run build

migrate:
	alembic upgrade head

benchmark:
	python scripts/benchmark.py sample-data/synthetic-ramp.mp4 --detector synthetic_color --fps 6

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache apps/web/.next test-storage test-aeroramp.db
