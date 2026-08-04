# GLK 3.1.0 Example

`appointment-run.yaml` shows two independent entry GO nodes activating together,
one join waiting on both D2 verdicts, and direct successor activation without an
intermediate scheduling queue. Every edge also demonstrates the 3.1.0
producer-to-consumer evidence bindings used by causal slicing.

The example pins the canonical method identity and shows the dual required GO/D2
and required CELL/D1 progress projection. Formal packages use the independent
templates under `glk/templates/` and are validated by `validate_run`.
