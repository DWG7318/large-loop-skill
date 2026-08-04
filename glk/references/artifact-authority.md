# Artifact Authority

GLK 3.0 uses independent append-only artifacts with one sole authority each.

| Object | Sole issuer/controller | Consumes | Forbidden authority |
|---|---|---|---|
| RUN_CONTRACT | LCCoding/Owner gateway | bounded product authority | technical verdicts |
| GLK_METHOD_LOCK | LCCoding/Owner gateway | canonical method identity | Run health |
| ROLE_BINDING | trusted registration adapter | external binding evidence | technical verdicts |
| GRAPH_BASELINE | Run Supervisor | frozen Run/GO contracts | D0-D3 |
| CELL_MANIFEST | Run Supervisor | exact GO required CELL set | CELL verdicts |
| D0 | Worker | exact CELL contract/candidate | D1-D3 |
| D1 | Checker | current manifest, exact candidate and D0 | D0/D2/D3 |
| SUPERVISOR_ADMISSION | Run Supervisor | exact artifact digest | changing its verdict |
| GO_CANDIDATE_CLOSURE | designated Worker | complete admitted CELL tuples | graph release |
| D2 | GO Verifier | exact current GO closure | successor release |
| GRAPH_EVENT | Run Supervisor | exact admitted D2 and graph | technical verdicts |
| D3 | Run Verifier | exact current required GO/D2 closure | Owner decision |
| OWNER_ACCEPTANCE | Owner | exact admitted current D3 | D0-D3 |
| SECURITY_HANDOFF | Run Supervisor | accepted Run candidate | security closure |
| CHECKER_PROGRESS_EVENT | Checker | exact D1 or GO closure trigger | technical verdicts |
| SUPERVISOR_PROGRESS_EVENT | Run Supervisor | exact Required-set/Graph/D2/D3/Owner trigger | technical verdicts |

`RUN_PACKAGE_INDEX`, `MONITOR_CONTROL`, and `PREFLIGHT_ADMISSION` are Supervisor
control artifacts, not technical or product verdicts. The Supervisor cannot issue,
hold issuance capability for, or invoke D0-D3.

Validation, preflight, simulation, migration, liveness, and progress projections
are derived non-authoritative. They are not formal artifacts and cannot advance
the Run by themselves. The two progress-event artifacts are append-only operational
trace inputs to those projections, never technical verdicts.

GLK 3.1 adds append-only operational controls with one issuer: Supervisor issues
`WORKER_CHECKER_WAKE_BINDING`, `DEVICE_CAPACITY_PROFILE`,
`CUMULATIVE_ENGINEERING_LOAD`, `CELL_WORK_ESTIMATE`, `CELL_CAPACITY_GATE`, and
`CELL_PLAN_AMENDMENT` and `SUPERVISOR_PROGRESS_EVENT`; Worker issues
`WAKE_ATTEMPT`, `PENDING_WAKE`, and `CELL_SCOPE_EXCEEDED`; Checker issues
`WAKE_ACK` and `CHECKER_PROGRESS_EVENT`. None may issue or replace D0-D3. Patrol
observations and layered progress projections remain derived non-authoritative.
