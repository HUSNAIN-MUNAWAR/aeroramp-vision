# Contributing

Thanks for considering a contribution to AeroRamp Vision.

## Ground rules

- Preserve the aviation disclaimer and human-review language.
- Do not add claims about production readiness, certification, security, compliance, accuracy, mAP, recall, or false-positive rates unless the repository contains evidence for the claim.
- Do not commit real airport video, passenger imagery, RTSP URLs, credentials, `.env` files, model checkpoints with unclear provenance, local databases, or generated storage artifacts.
- Keep detector outputs honest. Generic detectors must not relabel objects as airport-specific equipment without a validated model.
- New safety rules must document debounce, cooldown, confidence inputs, calibration requirements, and reviewer-facing wording.

## Development workflow

1. Create a focused branch.
2. Install dependencies with `py -3.12 -m pip install -e ".[dev]"` and `npm --prefix apps/web ci`.
3. Add or update tests for behavior changes.
4. Run the relevant checks:

```bash
py -3.12 -m ruff check .
py -3.12 -m mypy apps/api/aeroramp packages/sdk/python/aeroramp_sdk scripts
py -3.12 -m pytest
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

5. Open a pull request with a concise summary, validation notes, and screenshots for UI changes.
