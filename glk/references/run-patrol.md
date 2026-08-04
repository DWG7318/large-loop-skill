# One mechanical Run patrol

Each Run binds exactly one visible `RUN_PATROL_CONVERSATION` and one heartbeat through append-only `MONITOR_CONTROL`. The patrol uses `gpt-5.6-luna` with `xhigh`; light `LOW`, normal `MEDIUM`, and heavy `HIGH` map to 10, 15, and 30 minutes. The patrol is not a seventh authority role.

Every `patrol_cycle_id` contains exactly one evidenced closed row for unexplained Loop stoppage, unconsumed `PENDING_WAKE`, proven subagent misuse, forbidden Supervisor wait including wait-all, duplicate patrol/heartbeat, unauthorized or unknown task Pin provenance, and terminal closure. Missing, duplicate, free-form, or alert-suppressing rows fail closed. Formal pause, legal `BLOCKED`, external wait, and normal work do not alert. It emits fixed status, evidence, and alert codes; it does not inspect engineering quality, repair, accept, report progress, re-plan, take over, or re-dispatch.

GO, CELL, Round, plan step, visible stable same-project task, and the text `子任务` are not subagents. Only closed evidence of `spawn_agent`, `delegate_task`, hidden Agent, or background Agent is `SUBAGENT_USE_FORBIDDEN`. All six formal role profiles and Patrol exclude these capabilities; Patrol also excludes task creation, fork, delegation, and Pin.

No method role may call `set_thread_pinned(true)` or an equivalent operation. Only an explicit Owner manual UI choice or item-specific current-Run authorization is legal. Agent/method Pin evidence is `UNAUTHORIZED_THREAD_PIN`, even after Unpin. Unproved source is `PIN_PROVENANCE_UNKNOWN`; the patrol must not unpin because the Pin might be Owner-authored. Archive/unarchive and Pin are independent.

After formal Loop termination the sequence is `LOOP_TERMINAL`, heartbeat deletion, `PATROL_CLOSED`, then patrol-conversation archive.
