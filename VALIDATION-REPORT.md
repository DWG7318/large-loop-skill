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
- one Run patrol with LOW/MEDIUM/HIGH = 10/15/30, an exact seven-check cycle,
  bounded non-wait-all Supervisor snapshots, all-role subagent exclusion, and
  terminal closure;
- Owner-only Pin provenance with no automatic Unpin;
- append-only Checker/Supervisor progress-trigger coverage with layered D1 CELL and
  D2 GO counts and versioned denominator recomputation;
- device/cumulative-load CELL capacity gate, scope excess, and severe split feedback;
- resource-aware maximal-safe activation without fake dependency edges;
- ten technical validation layers plus mandatory Layer 11 for exact current 3.1
  method locks; only exact historical 3.0 locks are legacy `NOT_APPLICABLE`.

## Local machine results

Environment: Windows, Python 3.14, UTF-8 mode enabled.

Fresh GLK 3.1.0 acceptance evidence:

- complete repository suite executed as four disjoint file shards: `628 passed`
  (`73 + 109 + 263 + 183`);
- security-relevant optimized-Python matrix executed as three disjoint shards:
  `230 passed` (`44 + 88 + 98`), with only the expected pytest `-O` warning;
- CP936 with `PYTHONUTF8=0`: repository validator PASS and `54 passed`;
- repository distribution validator: `PASS`, scope `REPOSITORY_DISTRIBUTION`.

Repository-local structural evidence:

- current `glk/scripts` Python: `7,956` lines, down from `9,382` at the start of
  this continuation;
- active `docs/superpowers` surface: `355` lines; completed slice plans remain in
  Git history rather than the active method surface;
- `run_state.py` and the standalone progress executor are absent;
- the legacy mutable graph model is test-support-only; repository validation,
  hashing, release construction, and draft bootstrap implementations live under
  `tools/`, with the prior repository-validator command retained as a thin shim;
- native CELL capacity behavior remains current pending a real shared LCCoding
  control contract;
- focused post-migration gates: `146 passed`; repository/ZIP/structure gates after
  final hash refresh: `56 passed`; repository validator PASS.

The release gate runs the complete pytest suite, the R01-R28/positive suite under
normal and optimized Python, `validate_glk` with scope `REPOSITORY_DISTRIBUTION`,
real `validate_run` CLI cases with scope `RUN_PACKAGE`, CP936/UTF-8-off regression,
schema/template validation, hash verification, and acceptance ZIP integrity.

This is verified unreleased maintenance on the 3.1 code line, not a GLK 4.0 release
claim. Final 4.0 shared-control, validator-decomposition, distribution-size, and
release-identity gates remain open and no old tag or Release is overwritten.

The GitHub workflow repeats validation and all tests on Windows and Ubuntu using
Python 3.12. Repository text is pinned to LF so byte-level integrity hashes remain
stable across both checkout platforms. A release is mergeable only after both jobs
pass.

## Interpreting green tests

Green tests prove the executable 3.1.0 contracts shipped in this repository. They
do not accept product work, substitute for D1-D3, or claim that LCCoding's
centralized vulnerability closure has passed.
