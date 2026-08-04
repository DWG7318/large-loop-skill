# GLK 3.1.0 Validation Report

## Scope

- Owner-frozen six-role identity;
- fresh Run Supervisor binding per Run;
- directed acyclic GO graph;
- typed `WAITING_GO` reasons and direct activation;
- maximal safe multi-GO activation;
- evidence-bound D2 consumption edges;
- current-candidate/D2-bound causal sources and explicit real symptom sets;
- incident-evidence-selected paths with excluded alternative edges;
- typed candidate/evidence/claim-output impact seeds;
- strict typed-seed to source-disposition and invalidation consistency;
- minimum descendant invalidation and append-only receipt history;
- WAITING/ACTIVE maximal-parallel reactivation after repair;
- D1-before-D2, candidate identity, and context independence;
- formal resolution semantics;
- executable templates and JSON Schema;
- draft-only bootstrap, trusted preflight, and no-side-effect simulation;
- immutable complete Run package loading and ten validation layers;
- independent append-only D0/D1/admission/D2/graph-event/D3/Owner artifacts;
- exact CELL manifest and GO candidate closure;
- adapter-backed provenance, isolation, liveness, and architecture holds;
- canonical method lock and 2.4 formal-use freeze/migration;
- repository/version/semantic validation;
- hash manifest and clean ZIP construction;
- Windows/Linux UTF-8 CI matrix.
- Worker-only scoped wake Levels 1-4 with injected time and exact ACK cleanup;
- one Run patrol, bounded Supervisor waiting, subagent classification, and terminal closure;
- Owner-only Pin provenance with no automatic Unpin;
- layered D1 CELL and D2 GO progress with versioned denominator recomputation;
- device/cumulative-load CELL capacity gate, scope excess, and severe split feedback;
- resource-aware maximal-safe activation without fake dependency edges;
- ten technical validation layers plus the 3.1 operational-control gate.

## Local machine results

Environment: Windows, Python 3.14, UTF-8 mode enabled.

Fresh GLK 3.1.0 acceptance evidence:

- complete repository suite: `563 passed`;
- security-relevant optimized-Python matrix: `152 passed`;
- CP936 with `PYTHONUTF8=0`: repository validator PASS and `52 passed`;
- repository distribution validator: `PASS`, scope `REPOSITORY_DISTRIBUTION`.

The release gate runs the complete pytest suite, the R01-R28/positive suite under
normal and optimized Python, `validate_glk` with scope `REPOSITORY_DISTRIBUTION`,
real `validate_run` CLI cases with scope `RUN_PACKAGE`, CP936/UTF-8-off regression,
schema/template validation, hash verification, and acceptance ZIP integrity.

The GitHub workflow repeats validation and all tests on Windows and Ubuntu using
Python 3.12. Repository text is pinned to LF so byte-level integrity hashes remain
stable across both checkout platforms. A release is mergeable only after both jobs
pass.

## Interpreting green tests

Green tests prove the executable 3.1.0 contracts shipped in this repository. They
do not accept product work, substitute for D1-D3, or claim that LCCoding's
centralized vulnerability closure has passed.
