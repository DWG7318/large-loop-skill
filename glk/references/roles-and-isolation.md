# Roles and Isolation

## Six-role authority

| Authority | Role |
|---|---|
| Run contract control, GO graph, waiting reasons, activation, amendments | Run Supervisor |
| Product implementation and D0 | Worker |
| Immutable CELL validation and D1 | Checker |
| GO composition validation and D2 | GO Verifier |
| Run composition and graph-seam validation and D3 | Run Verifier |
| Product acceptance after D3 | Owner |

## Fresh Run Supervisor

Every Run creates a fresh Supervisor binding. Across two Runs, the following must
all differ:

```text
role_binding_id
instance_id
context_id
workspace_id
evidence_root
```

The same underlying model is not the same role instance and may be selected again
only through a new binding. A completed Run's Supervisor is archived and performs
no hidden work.

## Concurrent GO instances

The six role types do not limit instance count. Each concurrent ACTIVE_GO receives
isolated Worker, Checker, and GO Verifier bindings as needed. At minimum isolate:

- conversation and context;
- mutable workspace and runtime state;
- candidate path and evidence root;
- browser/database/port/temp resources;
- role lifecycle and decision inputs.

Checker never validates its own product edit. GO Verifier never shares the Checker
context. Run Verifier remains outside supervision, implementation, and checking.

GO Verifier and Run Verifier may use one underlying Agent only through separate
clean contexts, workspaces, evidence intake, and receipts; separate Agent instances
remain the default.
