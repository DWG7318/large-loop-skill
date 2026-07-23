# Verification and Evidence

## Three acceptance layers

```text
Worker receipt
  != CELL acceptance

CELL acceptance
  != GO verdict

GO verdict
  != project acceptance
```

Worker proves implementation-side work.

Checker independently validates one CELL candidate.

Verification independently judges the complete GO outcome.

Supervisor accepts the final graph composition.

## GO Verification Contract

Every GO defines before execution:

```text
GO_ID and version
Calabash trace
claim to prove
observable outcomes
required evidence
counter-evidence
pass/fail criteria
named frozen outputs
GO-boundary checks
environment definition
safety constraints
```

Verification never invents success criteria after construction.

## Pre-binding

Before a GO's first CELL:

- Supervisor provisions Verification capabilities and autonomy boundaries.
- Grapher indexes the binding on the GO node.
- a fresh attempt template, direct route, evidence path, and environment template
  are ready.

A concrete fresh Verification instance is activated before GO handoff.

## Direct handoff

After Router emits `GO_CANDIDATE_READY`, Checker sends a neutral package directly to
Verification. Supervisor does not relay or summarize.

Verification sends one signed verdict directly to Grapher and Supervisor and copies
the owning CELL roles.

## Verdicts

```text
GO_VERIFIED
GO_EVIDENCE_GAP
GO_REWORK_REQUIRED
GO_DEFINITION_DEFECT
GO_BLOCKED
GO_REJECTED
```

Only `GO_VERIFIED` allows Grapher to expose named outputs to successors.

## Evidence separation

Use separate append-only paths:

```text
evidence/worker/<cell>/<attempt>/
evidence/checker/<cell>/<attempt>/
evidence/verification/<go>/<attempt>/
evidence/grapher/<graph-version>/
evidence/supervisor/
```

One role's receipt does not satisfy another role's obligation.

## Candidate identity

Every receipt binds:

```text
Calabash hash
graph version/hash
GO/CELL/attempt
contract hash
candidate artifact identity
environment fingerprint
role/model binding
evidence hash
result/verdict
```

A material change invalidates prior evidence.

## Counter-evidence

Verification must actively check defined failure signals. A pile of positive tests is
not enough when the Contract identifies observable counter-evidence.

## GO rework

A rework verdict does not let Verification repair the product.

Planner creates new CELL work, Worker implements, Checker validates, Router routes,
and a changed GO candidate gets a fresh Verification attempt.
