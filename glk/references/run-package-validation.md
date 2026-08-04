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

GLK 3.1 keeps these ten technical layers and applies an operational-control gate
after them when 3.1 controls are present. It validates wake lineage, patrol
uniqueness, Pin capability exclusion, current capacity/load/estimate/gate lineage,
and severe post-dispatch split re-evaluation. Operational failure changes no D0-D3
verdict.
