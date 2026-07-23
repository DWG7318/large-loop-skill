# Changelog

## 2.0.0

- Rename Large Loop Skill (LLK) to Graph Loop Skill (GLK).
- Add mandatory Calabash / Minimum Calabash gate.
- Add project-level Grapher as sole GO Graph authority.
- Restrict Planner, Worker, Checker, and Router to CELL scope.
- Add isolated GO-scoped Verification as sole GO verdict authority.
- Add branches, joins, partial unlock, fallbacks, conflicts, and bounded cycles.
- Add graph versioning, READY/ACTIVE/BLOCKED sets, deadlock detection, and graph
  revision simulation.
- Add multiple eligible Workers per CELL with exactly one active Worker lease.
- Add immutable Worker handoff, switch, and collision recovery.
- Inherit MSLK 1.9 autonomy, isolation, GO evidence, no cross-GO CELL dependency,
  layered detection, append-only evidence, and Owner-exclusive escalation rules.
- Replace old Router-owned “Goal verified?” project closure with layered
  CELL Router -> GO Verification -> Grapher -> Supervisor authority.
