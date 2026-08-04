# Run Package Validation

`validate_glk` reports `REPOSITORY_DISTRIBUTION`; `validate_run` reports
`RUN_PACKAGE`. These scopes are not interchangeable.

The Run loader scans the complete declared formal roots and referenced evidence
roots. It recomputes file digests and exact inventory membership, verifies the
append-only `RUN_PACKAGE_INDEX` chain and unique head, rejects omissions, extra
unindexed formal objects, forks, path escape, symlinks, unknown formal types, and
duplicate digests, then deep-freezes the loaded subject.

The ten validation layers are:

1. serialization and schema;
2. package/index integrity;
3. Run/Graph/GO/CELL/reference identity;
4. adapter-backed provenance, authority, capability, and isolation;
5. candidate, digest, admission, and receipt lineage;
6. CELL manifest and GO candidate closure;
7. recomputed graph structure and acyclicity;
8. D2 admission and graph-event separation;
9. D3 closure, graph seams, and Run Verifier isolation;
10. Owner Acceptance and post-acceptance security handoff.

A `VALIDATION_REPORT` is derived non-authoritative. It cannot issue a receipt,
admission, graph event, D3, or Owner Acceptance. Package load failure is reported as
package/invocation failure, not as a fabricated technical verdict.

GLK 3.1 keeps these ten technical layers and requires Layer 11 whenever the exact
method lock is 3.1.0. Layer 11 validates exact wake lineage, the complete patrol
checklist and uniqueness, Pin and all-role subagent capability exclusion,
Supervisor wait-all/long-wait exclusion, current capacity/load/estimate/gate
lineage, severe post-dispatch split re-evaluation, and exact progress-trigger
coverage. Missing 3.1 controls fail closed; artifact absence cannot turn the layer
off. Only an exact historical 3.0 lock receives explicit legacy `NOT_APPLICABLE`.
Operational failure changes no D0-D3 verdict.
