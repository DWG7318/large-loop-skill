# Changelog

## 2.3.1

### Owner-frozen architecture

- Preserve exactly six roles: Run Supervisor, Worker, Checker, GO Verifier, Run
  Verifier, and Owner.
- Require a fresh Run Supervisor instance for every Run.
- Keep the GO execution graph acyclic.
- Remove the READY state and queue interpretation.
- Replace single-GO scheduling with a maximal safe ACTIVE_GO set.
- Require typed waiting reasons and prohibit arbitrary serialization or fake edges.
- Keep independent D0-D3 evidence layers, immediate Run Owner Acceptance, and the
  LCCoding security boundary.

### Engineering fixes

- Enforce D1-before-D2 and same-candidate bindings.
- Define formal resolution semantics for superseded/cancelled GO nodes.
- Add executable JSON Schema and eleven complete templates.
- Add a self-validating Run bootstrap.
- Add cross-platform UTF-8 tests, repository validation, and clean release tooling.
- Remove cache artifacts and obsolete 2.0.0 control-role contracts.

## 2.3.0 — withdrawn

The 2.3.0 candidate correctly introduced the six-role Run boundary and independent
D2/D3, but incorrectly specified multiple READY nodes with exactly one ACTIVE node.
Its state model, tests, validator, and package hygiene were incomplete. It must not
be installed or substituted for 2.3.1.

## 2.0.0

Historical seven-role GLK architecture. Existing historical receipts remain bound
to their original version and do not migrate automatically.
