# Security Boundary

GLK 3.1.0 remains a method contract, not a security or Agent runtime.

GLK owns only safety checks required by the frozen Run contract. It does not issue
centralized vulnerability closure.

After `LOOP_OWNER_ACCEPTED`, GLK emits `SECURITY_HANDOFF` with Run ID, candidate ID
and hash, audit scope, required Auditor binding, status, and post-security acceptance
requirement.

LCCoding owns the canonical security contract, independent project-wide audit,
engineering repair loop, Auditor re-verification, final closure, and Post-Security
Owner Acceptance. GLK's handoff never claims that this downstream work has passed.

The handoff may exist only after valid Owner Acceptance and remains
`PENDING_LCCODING_AUDIT`. Credentials, sessions, key custody, and production
runtime enforcement stay outside GLK.
