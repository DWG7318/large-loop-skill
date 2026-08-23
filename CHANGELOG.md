# Changelog

## 3.2.0

- Reconstructed GLK as a multi-start `ALL`-join DAG whose every GO executes through one Run-bound latest SLK baseline.
- Reduced the active method to one main Skill and three GLK-native child Skills; removed the old active runtime/kernel, duplicate roles, patrol, queues, and extra verification layers.
- Added `GLK-GRAPH.md`, `GLK-ROSTER.md`, and one shared `GLK-RUN-<RUN-ID>.md` as the complete Run-control file set.
- Made Fusion the sole owner of final code overlap, implementation conflict, and interface integration in an independent worktree.
- Kept one final D2 boundary and one prebuilt conditional D2 Repair GO while preserving ordinary D1 rework in the original GO pair.

## Historical unreleased 3.1 structural-maintenance notes

- Establish one current graph kernel and retire the duplicate `run_state.py` truth
  source plus the standalone progress executor.
- Move the legacy mutable graph model to compatibility-test support and move draft
  bootstrap, repository hashing, repository validation, and release construction
  implementations to root `tools/`; preserve the public repository-validator CLI as
  a thin shim.
- Keep native `cell_capacity.py` until a current shared LCCoding Loop-control
  contract owns that behavior; no capability is removed merely to meet a line goal.
- Reduce current `glk/scripts` Python from 9,382 to 7,956 lines and active
  Superpowers construction documents to 355 lines without weakening six-role,
  GO-DAG, D0-D3, causal, provenance, or fail-closed validation rules.

## 3.1.0

### Worker wake, patrol, progress, and capacity

- Add a Worker-only four-level original-Checker wake ladder with scoped CELL
  position, 120-second injected-clock windows, exact `WAKE_ACK`, one temporary
  heartbeat, and append-only `PENDING_WAKE` fallback.
- Prohibit Supervisor long/looping waits and add one visible non-authoritative Run
  patrol using `gpt-5.6-luna` with `xhigh`; light/normal/heavy map to 10/15/30
  minutes. Wait-all is always forbidden.
- Define GO/CELL/Round/plan steps and visible tasks as work units rather than
  subagents; reject actual spawn/delegate/hidden/background Agent evidence.
- Permanently remove Pin capability from every method role and patrol. Add
  `UNAUTHORIZED_THREAD_PIN` and `PIN_PROVENANCE_UNKNOWN` provenance alerts without
  automatic Unpin.
- Add layered Worker/Checker/Supervisor progress derived only from current D1/D2/D3
  and Owner facts; amendments recompute current Required denominators.
- Add versioned device capacity, cumulative engineering load, total-cost CELL
  estimates, three-state capacity gate, scope-exceeded return, and severe late-split
  re-planning.
- Extend maximal-safe activation with physical resource reservations without fake
  dependency edges, and add an operational-control gate after the ten technical
  Run-validation layers.
- Make Layer 11 mandatory for every exact 3.1 method lock, with exact seven-check
  patrol cycles, six-role subagent capability exclusion, and append-only
  Checker/Supervisor progress-trigger coverage. Exact historical 3.0 locks alone
  retain explicit legacy `NOT_APPLICABLE`.

## 3.0.0

### Authority and Run validation

- Freeze new formal use of 2.4 while preserving immutable history for migration.
- Split D0, D1, Supervisor admission, D2, graph event, D3, and Owner Acceptance
  into independent append-only artifacts with one authority each.
- Add versioned CELL manifests, exact GO candidate closure, and safe reuse of only
  unchanged current-valid CELL D1 evidence.
- Add immutable Run package loading, append-only index-chain verification, and ten
  cross-artifact validation layers.
- Add the four-operation provenance adapter contract without implementing an Agent
  runtime or credential system inside GLK.
- Add draft-only bootstrap, trusted preflight, no-side-effect simulation, liveness
  fail-closed behavior, monitor de-duplication, authority/architecture holds, and
  dual GO-D2/CELL-D1 progress.
- Pin the canonical repository, invocation, version, schema/Skill bundles, real Run
  validator source bundle, and adapter profile/contract through `GLK_METHOD_LOCK`.
- Preserve the six-role no-intermediate-queue GO DAG, maximal-safe parallel
  activation, and evidence-selected causal recovery.

## 2.4.0

### Causal GO-DAG recovery

- Bind every new D2 dependency edge to source claim/output refs, target
  input/assumption refs, and consumption evidence.
- Add versioned `GO_CAUSAL_TRACE` records that distinguish a confirmed causal source
  GO from downstream symptom GOs without adding node types, states, or roles.
- Trace incidents backward only over actual-consumption edges; suspected traces
  remain evidence and cannot invalidate receipts.
- Bind a confirmed source to its current candidate and D2 basis, require an explicit
  real symptom set, and select every causal edge with incident-bound evidence instead
  of inferring causality from reachability.
- Type amendment seeds as candidate, evidence, or claim/output refs; reject unrelated
  refs and revalidate paths, exclusions, and stopping evidence at application time.
- Enforce seed-to-source disposition consistency: candidate and claim/output seeds
  invalidate the current artifact and require rework/quarantine, evidence-only seeds
  may reverify, and mixed seeds retain the strictest requirement.
- Project the minimum changed-ref successor slice as `UNAFFECTED`, `REVERIFY`,
  `REWORK`, or `QUARANTINE` while preserving historical receipts append-only.
- Reuse WAITING_GO/ACTIVE_GO and the maximum-cardinality scheduler so repaired
  branches reactivate safely and concurrently without READY or full-graph replay.

### Preserved Owner baseline

- Keep exactly six roles, a fresh Run Supervisor per Run, an acyclic execution
  graph, D0-D3 independence, immediate Run Owner Acceptance, and the LCCoding
  security boundary.

## 2.3.1

### Owner-frozen architecture

- Preserve exactly six roles: Run Supervisor, Worker, Checker, GO Verifier, Run
  Verifier, and Owner.
- Require a fresh Run Supervisor instance for every Run.
- Keep the GO execution graph acyclic.
- Remove the READY state and queue interpretation.
- Replace single-GO scheduling with a maximal safe ACTIVE_GO set.
- Require typed waiting reasons and prohibit arbitrary serialization or fake edges.
- Keep independent D0-D3 evidence layers, immediate Run Owner Acceptance, and the
  LCCoding security boundary.

### Engineering fixes

- Enforce D1-before-D2 and same-candidate bindings.
- Define formal resolution semantics for superseded/cancelled GO nodes.
- Add executable JSON Schema and eleven complete templates.
- Add a self-validating Run bootstrap.
- Add cross-platform UTF-8 tests, repository validation, and clean release tooling.
- Remove cache artifacts and obsolete 2.0.0 control-role contracts.

## 2.3.0 — withdrawn

The 2.3.0 candidate correctly introduced the six-role Run boundary and independent
D2/D3, but incorrectly specified multiple READY nodes with exactly one ACTIVE node.
Its state model, tests, validator, and package hygiene were incomplete. It must not
be installed or substituted for 2.3.1.

## 2.0.0

Historical seven-role GLK architecture. Existing historical receipts remain bound
to their original version and do not migrate automatically.
