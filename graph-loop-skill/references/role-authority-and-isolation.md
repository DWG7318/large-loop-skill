# Role Authority and Isolation

## Authority matrix

| Decision | Sole authority |
|---|---|
| Calabash baseline and project authority | Supervisor |
| GO Graph structure, READY set, and graph route | Grapher |
| Current CELL Contract and Worker recommendation | Planner |
| Product implementation under active lease | Worker |
| CELL factual validation | Checker |
| CELL route and Worker switch authorization | Router |
| GO evidence verdict | Verification |
| Graph amendment freeze and final project audit | Supervisor |

No role substitutes for another because another role is unavailable.

## Isolation identity

Every instance records:

```text
role_id
conversation_id
context_id
workspace_id
runtime_namespace
capability_profile_id
model_binding_id
evidence_path
lifecycle_state
authority_scope
```

Different conversation titles alone are insufficient.

## Environment boundaries

- Supervisor uses control and contract artifacts.
- Grapher uses graph state, signed GO verdicts, and graph evidence.
- Planner uses the activated GO Contract and CELL planning workspace.
- each Worker uses a separate implementation workspace;
- Checker validates a frozen CELL candidate in a clean environment;
- Router consumes formal records and writes routes only;
- Verification validates a frozen GO candidate in a fresh clean environment.

When relevant, separate database/schema, ports, browser profiles, temp directories,
mutable caches, service processes, logs, and generated markers.

Read-only content-addressed caches may be shared.

## Information boundaries

### Verification receives

- Calabash baseline and GO trace;
- GO Verification Contract;
- immutable candidate and frozen inputs;
- accepted CELL receipt index;
- neutral evidence index;
- environment definition and allowed verification commands.

It does not initially receive:

- Checker recommendation or confidence;
- Worker/Checker transcript;
- hidden reasoning;
- mutable state;
- prior unrelated verdicts.

### Grapher receives

- signed GO verdicts;
- frozen named outputs;
- graph events and resource/conflict state;
- formal block and defect records.

It does not receive hidden Planner/Router reasoning as graph authority.

## Same-model use

The same underlying model family is allowed only with distinct model-binding IDs,
contexts, workspaces, evidence, and role instructions.

Model diversity improves defense but does not replace procedural isolation.

## Contamination

Record the appropriate violation and invalidate affected decisions:

```text
ROLE_ISOLATION_VIOLATION
CHECKER_ENVIRONMENT_VIOLATION
VERIFICATION_ISOLATION_VIOLATION
GRAPHER_AUTHORITY_CONTAMINATION
ACTIVE_WORKER_COLLISION
```

Restore from the last valid immutable state and rerun affected gates.
