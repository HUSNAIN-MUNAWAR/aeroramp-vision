from __future__ import annotations

import logging
import signal
import time

from aeroramp.core.logging import configure_logging
from aeroramp.db.models import ProcessingJob
from aeroramp.db.session import SessionLocal
from aeroramp.services.processing import run_processing_job
from sqlalchemy import select

configure_logging()
logger = logging.getLogger("aeroramp.worker")
running = True


def stop(*_: object) -> None:
    global running
    running = False


def main() -> None:
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    logger.info("worker_started")
    while running:
        with SessionLocal() as db:
            job = db.scalar(select(ProcessingJob).where(ProcessingJob.status == "queued").order_by(ProcessingJob.created_at).limit(1))
        if job:
            try:
                run_processing_job(job.id)
            except Exception:
                logger.exception("worker_job_failed", extra={"job_id": job.id})
        else:
            time.sleep(1.5)
    logger.info("worker_stopped")


if __name__ == "__main__":
    main()
