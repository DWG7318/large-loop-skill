# One mechanical Run patrol

Each Run binds exactly one visible `RUN_PATROL_CONVERSATION` and one heartbeat through append-only `MONITOR_CONTROL`. The patrol uses `gpt-5.6-luna` with `xhigh`; frozen project difficulty maps HIGH/MEDIUM/LOW to 10/15/30 minutes. The patrol is not a seventh authority role.

It checks only unexplained Loop stoppage, unconsumed `PENDING_WAKE`, proven subagent misuse, forbidden Supervisor wait, duplicate patrol/heartbeat, unauthorized or unknown task Pin provenance, and missing terminal closure. Formal pause, legal `BLOCKED`, external wait, and normal work do not alert. It emits fixed status, evidence, and alert codes; it does not inspect engineering quality, repair, accept, re-plan, take over, or re-dispatch.

GO, CELL, Round, plan step, visible stable same-project task, and the text `子任务` are not subagents. Only closed evidence of `spawn_agent`, `delegate_task`, hidden Agent, or background Agent is `SUBAGENT_USE_FORBIDDEN`. Patrol capabilities exclude task creation, fork, delegation, subagents, and Pin.

No method role may call `set_thread_pinned(true)` or an equivalent operation. Only an explicit Owner manual UI choice or item-specific current-Run authorization is legal. Agent/method Pin evidence is `UNAUTHORIZED_THREAD_PIN`, even after Unpin. Unproved source is `PIN_PROVENANCE_UNKNOWN`; the patrol must not unpin because the Pin might be Owner-authored. Archive/unarchive and Pin are independent.

After formal Loop termination the sequence is `LOOP_TERMINAL`, heartbeat deletion, `PATROL_CLOSED`, then patrol-conversation archive.
