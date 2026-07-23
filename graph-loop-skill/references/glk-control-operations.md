# GLK Control Operations

## Start

`GLK START` is manual and applies only to a prepared project with:

- frozen Calabash;
- frozen graph version;
- readiness receipts;
- simulation pass;
- autonomy envelope;
- role/environment bindings.

Starting does not authorize production deployment or destructive external actions.

## Pause

Pause at safe boundaries:

- before a new GO activation;
- before a new Worker lease;
- after a Worker receipt;
- after a Checker verdict;
- after a GO verdict.

Do not interrupt a mutable write without checkpoint and lease handling.

## Resume

Resume requires:

- same or formally replaced role binding;
- current graph version;
- current active/ready sets;
- valid Worker lease or no lease;
- fresh environment validation;
- no stale candidate or verdict.

## Graph control commands

Valid project control records include:

```text
GLK_START
GRAPH_NODE_ACTIVATE
GRAPH_NODE_DEFER
GRAPH_ROUTE_APPLY
GRAPH_AMENDMENT_PROPOSED
GRAPH_REVISION_SIMULATION_PASS
GRAPH_REVISION_ACTIVATE
GLK_PAUSE
GLK_RESUME
GOVERNANCE_HOLD
GRAPH_TERMINAL_REACHED
PROJECT_ACCEPTED
```

## Worker control records

```text
WORKER_LEASE_GRANTED
WORKER_LEASE_REVOKED
WORKER_SWITCH
ACTIVE_WORKER_COLLISION
WORKER_EXECUTION_FAILURE
```

## Idempotence

Every control command has a unique command ID, graph/CELL version, expected prior
state, result, and evidence reference. Repeating the same command must not double
activate a GO or create two Worker leases.

## Safeguard patrol

Supervisor may inspect control health, role availability, graph progress, and hard
brakes. It does not route GOs, validate CELLs, or take over Worker implementation.

Grapher may inspect graph readiness and route records. It does not inspect mutable
Worker workspaces or inject into active Verification.
