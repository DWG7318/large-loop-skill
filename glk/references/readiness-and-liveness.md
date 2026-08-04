# Readiness and Liveness

Bootstrap creates only `DRAFT_SCAFFOLD` and unresolved draft instances. It never
indexes placeholder hashes or calls a template collection a complete Run.

Formal preflight requires:

- an exact canonical method lock and one declared installation;
- complete six-role bindings and capability profiles;
- trusted adapter verification of Supervisor non-issuance for D0-D3;
- conversation, context, workspace, runtime-state, evidence-root, and
  decision-input isolation;
- valid indexed evidence roots and separated writable scopes;
- a ten-layer valid package;
- readiness observations for exactly the bound roles;
- a no-side-effect simulation and no active hold.

`PREFLIGHT_REPORT` and `SIMULATION_REPORT` are derived non-authoritative. A
Supervisor may mechanically admit their exact digests only after recomputation.

Liveness consumes indexed `check_liveness` attestations bound to the exact Run,
role, adapter profile, and observation deadline. Missing reads, stale evidence, or
deadline expiry never imply health. An expired role becomes unreachable.

`MONITOR_CONTROL` has one deterministic monitor key and one append-only head. It
references the existing Supervisor task/callback, binds the exact current
attestation set, and never creates or schedules a second task. Technical authority
violations produce `RUN_AUTHORITY_HOLD`; repeated HIGH architecture findings on the
same path produce `RUN_ARCHITECTURE_HOLD`.

Progress reports exact `required GO/D2` and `required CELL/D1` counts and IDs,
active GO IDs, typed waiting reasons, unreachable bindings, current holds, graph
version, and CELL manifest versions.
