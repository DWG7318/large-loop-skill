# Migration to GLK 2.4.0

## Hard boundary

GLK 2.4.0 preserves the Owner-approved 2.3.1 six-role architecture and adds
evidence-bound causal recovery. Historical Runs remain
governed by the version under which their contracts and receipts were frozen.
No historical version may be silently relabeled as 2.4.0.

## From 2.3.1

Existing 2.3.1 graphs remain readable for ordinary scheduling. To use 2.4.0 causal
recovery, create a new graph/schema version and bind every participating D2 edge to
source claim/output refs, target input/assumption refs, and consumption evidence.

Do not infer a causal source from ancestor position. Record `GO_CAUSAL_TRACE` with
`SUSPECTED` or `CONFIRMED`; only the latter can authorize a minimum impact slice.
Preserve historical candidates and receipts append-only while marking their
current-validity for the new version. Re-project affected GOs through existing
`WAITING_GO` and `ACTIVE_GO`; do not introduce READY, a Barrier, or full-graph replay.

## From withdrawn 2.3.0

| 2.3.0 object | 2.3.1 rule |
|---|---|
| READY GO | Remove; use `WAITING_GO` with reasons or direct `ACTIVE_GO` |
| exactly one ACTIVE GO | Replace with maximal safe `ACTIVE_GO` set |
| scheduling choice among READY | Automatic activation; choice only inside real conflict sets |
| free-text independent context | Versioned role binding plus execution-context reference |
| direct `d2_pass()` | Require same-candidate D1 PASS and independent GO Verifier context |
| `SUPERSEDED`/`CANCELLED` counted terminal | Require formal resolution and amendment semantics |
| four-file bootstrap | Replace with all contracts, schema validation, and evidence directories |
| keyword validator | Replace with structural, semantic, schema, hash, and hygiene validation |

Any in-progress 2.3.0 Run must stop, preserve artifacts, create a new 2.3.1 Run
contract with a fresh Supervisor, and rebind still-valid immutable evidence. No
technical verdict transfers without candidate/hash and contract validation.

## From 2.0.0

The following role types are not part of 2.3.1:

```text
Grapher
Planner
Router
```

Their old authority is not assigned to new hidden roles. Run Supervisor owns the GO
graph, waiting reasons, activation, receipt routing, and amendments while remaining
forbidden from signing D1-D3. Worker, Checker, GO Verifier, Run Verifier, and Owner
retain separate technical/product authority.

The 2.0.0 conditional, fallback, conflict-edge, and loop-back graph contracts do not
transfer. Reconstruct one acyclic D2 precedence graph from the frozen 2.3.1 Run
Feature. Preserve historical receipts as immutable evidence only; re-verify any
claim consumed by the new candidate.

## Version and identity checks

Before starting a 2.4.0 Run, verify:

- `VERSION`, Skill front matter, SPEC, MANIFEST, templates, and Schema all say
  `2.4.0`;
- the six role bindings are used and no undeclared control role exists;
- the Supervisor binding is new for this Run;
- no normative READY state exists;
- the initial maximal safe active set is recorded;
- every waiting GO has typed evidence-backed reasons;
- every new D2 edge has complete actual-consumption bindings;
- suspected causal traces cannot invalidate receipts;
- causal amendments record minimum impact and reactivation projections;
- execution graph acyclicity and Run Feature coverage pass;
- D0-D3 candidate and context bindings are executable;
- Owner Acceptance and security handoff templates are available.
