# Calabash and GO Graph

## Definition order

```text
Owner intent / project evidence
        ↓
PROJECT_CALABASH_BASELINE
        ↓
PROJECT_GO_GRAPH
        ↓
GO_CALABASH_TRACE + EDGE_AUTHORITY_TRACE
        ↓
GO Verification Contracts
        ↓
CELL execution and graph routing
```

## Minimum Calabash

Minimum Calabash is:

```text
Grandpa -> Product Architecture -> Ontology
```

Grandpa defines purpose, value, boundaries, success direction, and non-negotiable
Owner judgments.

Product Architecture defines roles, entry points, business journey, product surfaces,
back-office support, data/evidence flow, external capabilities, and outcomes.

Ontology defines canonical concepts, relationships, ownership, states, and lifecycle.

Minimum Calabash defines what the product is. It does not itself define the GO graph,
CELL plan, role routing, or implementation.

## Establishing a missing baseline

Supervisor derives Minimum Calabash from authoritative sources:

- explicit Owner statements;
- approved product documents;
- current UI and journeys;
- stable domain models;
- verified contracts, workflows, and behavior;
- audit and acceptance evidence.

Supervisor may reconcile names and fill one uniquely supported interpretation. It may
not choose between materially different product meanings.

An irreducible ambiguity is `CALABASH_DEFINITION_BLOCKED`.

## GO trace

Every node records:

```text
GO_CALABASH_TRACE
GO_ID
Calabash version/hash
Grandpa source
Product Architecture source
Ontology concepts/states
derived outcome claim
verification implications
```

## Edge trace

Every edge records:

```text
EDGE_AUTHORITY_TRACE
edge_id
source GO(s)
target GO
edge type
Calabash source or verified runtime fact
required verdict/output
predicate
evidence source
invalidation rule
```

A graph edge cannot be justified only by implementation convenience.

## Graph semantics

### Nodes

Only complete independently verifiable GO outcomes are graph nodes.

CELLs remain private to one GO. A CELL is never a cross-GO dependency endpoint.

### Hard dependency

Target requires one or more source GOs to be `GO_VERIFIED` and may require named
frozen outputs.

### Conditional branch

A branch predicate must be frozen before source execution and evaluated from recorded
evidence. Grapher may not rewrite a predicate after seeing the desired path.

### Joins

- `JOIN_ALL`: every required predecessor verified.
- `JOIN_ANY`: one permitted predecessor verified.
- `JOIN_QUORUM`: a frozen count/weight threshold is met.

A join records which inputs participated.

### Fallback

A fallback path is frozen before failure. It is not an excuse to invent a new product
direction after a rejection.

### Conflict

Conflict edges/groups prevent unsafe concurrent activation but do not imply data
dependency.

### Loop back

Cycles are allowed only with a bounded contract. Each iteration creates append-only
records and cannot erase earlier failure evidence.

## READY computation

A GO is READY when:

- its node version is current;
- every required predecessor verdict/output exists;
- branch/join predicates pass;
- no conflict lock prevents activation;
- required Verification and role bindings are ready;
- autonomy and safety gates pass;
- the node is not stale, superseded, skipped, or terminally rejected.

Grapher owns READY computation.

## Graph amendment

A graph amendment must preserve traceability and state exactly what changes:

- node/edge additions, removals, or supersession;
- affected outputs and consumers;
- accepted evidence that remains valid;
- required re-verification;
- terminal reachability;
- cycle and conflict effects;
- Calabash continuity.

Supervisor freezes only after no-side-effect simulation passes.
