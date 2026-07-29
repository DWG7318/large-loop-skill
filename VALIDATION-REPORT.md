# GLK 2.3.1 Validation Report

## Scope

- Owner-frozen six-role identity;
- fresh Run Supervisor binding per Run;
- directed acyclic GO graph;
- typed `WAITING_GO` reasons and direct activation;
- maximal safe multi-GO activation;
- D1-before-D2, candidate identity, and context independence;
- formal resolution semantics;
- executable templates and JSON Schema;
- complete self-validating bootstrap;
- repository/version/semantic validation;
- hash manifest and clean ZIP construction;
- Windows/Linux UTF-8 CI matrix.

## Local machine results

Environment: Windows, Python 3.14, UTF-8 mode enabled.

```text
PASS: 38 pytest cases
PASS: repository structure and canonical semantics
PASS: all 11 templates against Draft 2020-12 Schema
PASS: hash manifest path and content verification
PASS: ZIP integrity and cache exclusion
```

The GitHub workflow repeats validation and all tests on Windows and Ubuntu using
Python 3.12. Repository text is pinned to LF so byte-level integrity hashes remain
stable across both checkout platforms. A release is mergeable only after both jobs
pass.

## Interpreting green tests

Green tests prove the executable 2.3.1 contracts shipped in this repository. They
do not accept product work, substitute for D1-D3, or claim that LCCoding's
centralized vulnerability closure has passed.
