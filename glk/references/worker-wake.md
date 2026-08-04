# Worker-only Checker wake

Only a Worker that has finished its current formal CELL may wake the original Checker frozen at dispatch. The four-level sequence is fixed:

1. T+0 sends `GO <GO_ID> CELL <ordinal>/<Required CELL total> 已交付，请检查` to the frozen Checker thread and host, then waits at most 120 seconds.
2. T+2 reads/lists the same task, validates host and binding, may unarchive it, and resends to the same Checker. It never guesses an ID or creates a replacement.
3. T+4 upserts one deterministic temporary Checker heartbeat without creating a conversation, then waits at most 120 seconds.
4. T+6 appends one `PENDING_WAKE` with the complete Run/GO/CELL/Round identity and three attempts.

The Checker first returns `WAKE_ACK` bound to Run, GO, CELL, Round, Checker binding, thread, and host. A matching ACK or mechanical proof that the same Checker started the same scope stops escalation, removes the temporary heartbeat, and consumes a matching pending record. Replays are idempotent.

The Worker must prove `send_message_to_thread`, `read_thread`, `list_threads`, `unarchive_thread`, bounded ACK wait, temporary heartbeat upsert/delete, and pending-wake write capabilities before dispatch. Any other role receives `WAKE_ROLE_FORBIDDEN`. This is not a general role message bus.

`BLOCKED` and `EXECUTION_FAILURE` use the same scope and ordinal. Rework of the same CELL does not change the ordinal or accepted count. Tests use an injected clock; the method never sleeps for real time.
