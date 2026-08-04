# Supply Chain and Migration

Until an Owner-approved migration changes it, the canonical identity is:

```text
repository: https://github.com/DWG7318/large-loop-skill
invocation: graph-loop-skill
version: 3.1.0
tag: v3.1.0
```

`GLK_METHOD_LOCK` binds exact commit/tag, schema bundle, Skill package, the real
Run validator source-bundle digest, adapter profile, and adapter contract version.
Preflight verifies only caller-declared installation roots and rejects missing,
duplicate, stale, or mismatched installations as `GLK_SUPPLY_CHAIN_CONFLICT`. It
does not search undeclared roots, fetch GitHub, or install software.

The 2.4 formal-use freeze rejects new formal 2.4 Runs. Migration may preserve
semantically compatible GO topology, actual-consumption edges, causal history, and
amendment history. Contracts, graph baselines, bindings, and receipts require fresh
3.0 validation or remain historical-only.

Mixed mutable CELL/GO receipts, combined receipt constructs, and sample/bootstrap
pass claims are not current formal types. A migration report is derived
non-authoritative, emits draft references only, never mutates history, and never
upgrades unproven 2.4 evidence into current evidence.

GLK defines only the four adapter operations `resolve_binding`, `verify_issuance`,
`verify_isolation`, and `check_liveness`. Credentials, sessions, issuance,
replay/checkpoint, Broker, and runtime provenance belong to LCagent or another
trusted execution environment. LCCoding owns lifecycle and centralized security
routing.
