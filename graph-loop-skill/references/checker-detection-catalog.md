# GLK Detection Catalog

Select only provisioned capabilities and allocate them to explicit tiers.

## Structural and dependency

- CodeGraph or equivalent structural graph
- import/dependency cycle checks
- API/schema/event compatibility
- database migration compatibility
- graph named-output compatibility

## Build and tests

- native build/type/lint
- unit/integration/contract tests
- browser/end-to-end checks
- mutation/coverage when risk-appropriate
- performance/load checks when acceptance requires them

## Security and supply chain

- Semgrep/CodeQL
- secret scanning
- OSV/Trivy or equivalent dependency scanning
- permission and policy tests
- destructive/external-action guards

## Graph-specific checks

- predecessor/output identity
- branch predicate reproduction
- join membership and threshold
- conflict lock release
- bounded-loop invariant and iteration count
- terminal reachability
- orphan/stale node detection

## Evidence

Every invocation records exact tool/version/configuration, input identity, trigger,
result, evidence path, and owning role.
