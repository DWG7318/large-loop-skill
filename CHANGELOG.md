# Changelog

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
