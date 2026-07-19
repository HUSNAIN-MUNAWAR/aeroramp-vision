# Security policy

## Threat model

AeroRamp Vision handles security-sensitive camera URLs, uploaded video, evidence, model files, operational events, and role assignments. Primary risks include credential disclosure, tenant leakage, malicious uploads, unsafe model deserialization, path traversal, unauthorized evidence export, edge impersonation, RTSP credential interception, dependency compromise, and privacy misuse.

## Implemented controls

- PBKDF2-SHA256 passwords with per-user random salts and high iteration count
- Signed short-lived access JWTs and refresh JWTs
- Tenant membership verification on every authenticated request
- Permission checks at route boundaries and tenant checks in services
- Encrypted stream URLs using a key derived from the deployment secret
- Filename sanitization, extension checks, upload size limits, decode validation, and storage-root checks
- SQLAlchemy parameterization
- Security headers, trusted hosts, CORS allowlist, request IDs, and in-process rate limiting
- Protected evidence endpoints; no direct storage directory exposure
- Auditing for login, configuration, review, correction, and export-sensitive actions
- ONNX/safetensors preference and explicit warning for pickle-based checkpoints
- No face recognition, biometric identity, or worker scoring

## Production hardening

Use a secrets manager, rotate JWT and edge credentials, enforce TLS/mTLS, use object-storage signed URLs, deploy malware scanning and media transcoding isolation, run model conversion in a sandbox, enable PostgreSQL row-level security as defense in depth, place RTSP traffic on a restricted network, use per-node certificates, enable centralized WAF/rate limiting, run dependency and container scanning, and establish incident response and key revocation.

Report vulnerabilities privately to the repository owner. Do not include airport credentials, passenger imagery, or exploitable details in a public issue.
