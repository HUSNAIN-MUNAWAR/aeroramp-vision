# Security model

## Authentication and authorization

User passwords are salted and hashed with PBKDF2-SHA256. Access and refresh JWTs are signed with a configured secret. Token organization and role are not trusted alone: the exact active user membership is checked against the database on each request. Permissions are enforced at endpoint/service boundaries and data reads are tenant scoped.

Edge nodes use a separate PBKDF2-hashed API key and `X-Edge-Key`; browser JWTs are not used as node identity.

## Upload and storage controls

Video names are sanitized, extensions are allowlisted, size is bounded during streaming upload, metadata is decoded before persistence, and invalid/corrupt media is rejected. Evidence paths are resolved and constrained under the configured evidence root. Camera stream URLs are Fernet encrypted using a key derived from the deployment secret and are omitted from camera responses.

## Model files

Only administrators with `models.manage` may register models. Safe registration accepts ONNX or safetensors by default, records a checksum and class list, and rejects an unexpected serialized extension. Loading pickle-based checkpoints remains an explicit isolated-review risk and is not accepted by the registration CLI.

## Web controls

The API applies trusted-host checks, configured CORS, per-process request rate limiting, request IDs, `nosniff`, frame denial, referrer policy, permissions policy, and a content-security policy. Production deployments should move rate limiting to a shared gateway, rotate refresh tokens, implement token revocation, terminate TLS, and use a secrets manager.

See `SECURITY.md` for threat scenarios, reporting, and deployment hardening.
