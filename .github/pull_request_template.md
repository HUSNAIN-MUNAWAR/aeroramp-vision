## Summary

- 

## Validation

- [ ] `py -3.12 -m ruff check .`
- [ ] `py -3.12 -m mypy apps/api/aeroramp packages/sdk/python/aeroramp_sdk scripts`
- [ ] `py -3.12 -m pytest`
- [ ] `npm --prefix apps/web run lint`
- [ ] `npm --prefix apps/web run typecheck`
- [ ] `npm --prefix apps/web run build`

## Safety and privacy checklist

- [ ] No `.env` files, credentials, RTSP URLs, local databases, or private media are included.
- [ ] Aviation decision-support wording remains accurate.
- [ ] Detector/model claims are supported by code or documented evidence.
- [ ] UI changes include screenshots when relevant.
