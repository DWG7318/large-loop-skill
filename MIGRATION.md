# Migration to GLK 3.0.0

## Formal-use freeze

New formal 2.4.x Runs are frozen. Historical Runs remain governed by the version
under which their contracts and evidence were produced. Migration never rewrites
history or silently relabels an old artifact as 3.0.0.

The canonical 3.0 identity is:

```text
https://github.com/DWG7318/large-loop-skill
graph-loop-skill
3.0.0
v3.0.0
```

## Preserve when semantically compatible

- the six roles and fresh Run Supervisor principle;
- GO-DAG topology and maximal-safe `WAITING_GO`/`ACTIVE_GO` scheduling;
- D0-D3 layer meanings and immediate Owner Acceptance;
- actual-consumption edges, evidence-selected causal traces, impact slices, and
  reactivation history;
- immutable historical evidence and repository hash discipline.

Preservation keeps facts available; it does not preserve derived trust.

## Convert and revalidate

- Run and GO contracts;
- graph baselines, amendments, formal resolutions, and indexes;
- role bindings through the trusted four-operation adapter;
- CELL required sets as versioned `CELL_MANIFEST` artifacts;
- CELL candidates as independent D0 and D1 artifacts plus exact admissions;
- GO candidates as `GO_CANDIDATE_CLOSURE`, D2, D2 admission, and graph event;
- Run closure as D3, D3 admission, Owner Acceptance, and security handoff.

The 3.0 loader and ten-layer validator recompute identity, digests, graph structure,
required sets, provenance, lineage, isolation, and current-validity.

## Historical-only

- 2.4 free-form role-binding strings;
- 2.4 D0-D3 evidence without trusted 3.0 provenance;
- old control ledgers and validation reports;
- old bootstrap workspaces and template-level completion claims;
- unproven 2.4 receipts of any kind.

Historical-only artifacts remain immutable audit evidence and cannot satisfy a 3.0
admission or closure.

## Rejected as current formal constructs

- combined `CELL_RECEIPT`, `GO_RECEIPT`, and `RUN_RECEIPT` templates;
- mixed mutable technical and control authority in one object;
- a hand-written `acyclic: true` value as proof;
- free actor strings or receipt IDs without digest-bound provenance;
- sample bootstrap PASS/READY/ACCEPTED claims;
- health inferred from failed reads;
- standalone or duplicate cron monitoring.

These constructs may remain mentioned in migration or rejection evidence but are
not accepted by the current formal registry.

## Migration report boundary

`derive_migration_report` emits a derived, non-authoritative classification and new
draft references only. It cannot admit an artifact, advance a state, mutate the old
package, or mark old evidence current-valid.

Compatible GO topology and causal history may be classified `preserve`; contracts
may be `revalidate`; old bindings and receipts may be `historical-only`; mixed
receipt/bootstrap constructs are discarded from formal eligibility. An unproven
2.4 artifact never becomes current evidence through classification.

## External boundaries

LCCoding owns project lifecycle, product-definition routing, centralized security,
and delivery. LCagent or another trusted environment owns sessions, credentials,
issuance, replay/checkpoint, Broker, and runtime provenance. GLK defines only the
method contract, validation logic, and abstract adapter interface.
