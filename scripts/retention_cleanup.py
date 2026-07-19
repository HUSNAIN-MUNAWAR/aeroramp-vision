from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aeroramp.db.models import EvidenceAsset, UploadedVideo
from aeroramp.db.session import SessionLocal
from sqlalchemy import select


def cleanup(raw_video_days: int, evidence_days: int, dry_run: bool = True) -> dict[str, int]:
    now = datetime.now(UTC)
    deleted = {"raw_videos": 0, "evidence_assets": 0}
    with SessionLocal() as db:
        videos = list(db.scalars(select(UploadedVideo).where(UploadedVideo.created_at < now - timedelta(days=raw_video_days))))
        assets = list(db.scalars(select(EvidenceAsset).where(EvidenceAsset.created_at < now - timedelta(days=evidence_days))))
        for video_row in videos:
            if not dry_run:
                Path(video_row.storage_path).unlink(missing_ok=True)
                db.delete(video_row)
            deleted["raw_videos"] += 1
        for asset_row in assets:
            if not dry_run:
                Path(asset_row.storage_path).unlink(missing_ok=True)
                db.delete(asset_row)
            deleted["evidence_assets"] += 1
        if not dry_run:
            db.commit()
    return deleted


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-video-days", type=int, default=30)
    parser.add_argument("--evidence-days", type=int, default=90)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(cleanup(args.raw_video_days, args.evidence_days, dry_run=not args.apply))
