# Detection, Autonomy, and Recovery

## Detection capability manifest

Before formal work, record every actually available skill/tool, version, configuration,
permission, evidence type, compute cost, and omission reason.

Naming an unavailable tool is not provisioning.

## Detection tiers

### CELL_ALWAYS

Fast checks that must run for every candidate.

### CELL_TRIGGERED

Checks selected by a frozen impact predicate. `NOT_TRIGGERED` requires predicate
evidence.

### GO_BOUNDARY

Complete GO checks owned by fresh Verification.

### GRAPH_EDGE

Checks for named output compatibility, branch predicates, joins, conflict release,
loop invariants, and downstream consumption.

### PROJECT_FINAL

Final composition, security, release, migration, and handoff checks.

## Product repair

Worker owns substantive product repair.

Checker may fix only Checker-owned validation harness or evidence-path defects, then
restart validation from a clean environment.

## Autonomy

Routine work is pre-authorized by `PROJECT_AUTONOMY_ENVELOPE`.

Internal roles must resolve ordinary:

- failed tests;
- implementation choices;
- Worker switches;
- evidence collection;
- graph scheduling;
- recoverable tool/environment problems;
- bounded rework.

Only Supervisor may request Owner assistance for a proven Owner-exclusive matter.

## Owner request format

```text
OWNER_ASSISTANCE_REQUIRED
one exact decision/action
evidence of Owner exclusivity
consequence of no action
safest available choices
```

Generic confirmation is invalid.

## Recovery principles

- never infer success from silence;
- preserve append-only state;
- freeze mutable work before replacement;
- restore from exact artifacts and hashes;
- rerun invalidated role readiness and simulation;
- do not substitute one authority for another.

## Graph deadlock analysis

Grapher checks:

- unmet hard dependencies;
- impossible predicates;
- join thresholds;
- conflict locks;
- exhausted cycles;
- stale or rejected source outputs;
- unreachable terminal nodes;
- missing Verification bindings.

Deadlock produces evidence and a graph-amendment proposal or hard brake, never a
fabricated route.
