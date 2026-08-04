# Run Owner Acceptance

GLK 3.0.0 Owner Acceptance consumes one exact current D3 PASS and its independent
Supervisor admission, both bound to the current package/index head.

Every GLK Run receives one small Owner Acceptance immediately after D3 PASS. It is
not postponed or merged into a project-end acceptance.

Run Supervisor provides:

- exact candidate identity and hash;
- bounded Run Feature and entry points;
- concise exercise steps and expected visible outcomes;
- known limitations;
- D3-covered invisible risks;
- role and receipt index.

Allowed verdicts are `LOOP_OWNER_ACCEPTED`, `LOOP_PRODUCT_REWORK`,
`PRODUCT_DEFINITION_CHANGE`, and `NEW_FEATURE_REQUEST`.

Only `LOOP_OWNER_ACCEPTED` completes the Run and permits the standardized LCCoding
security handoff.

D3 FAIL or BLOCKED, stale D3 generation, missing admission, wrong package head, or
invalid Run Verifier isolation fails closed. Only the Owner issues the acceptance
artifact. A following handoff remains `PENDING_LCCODING_AUDIT` until LCCoding
completes its independent security work.
