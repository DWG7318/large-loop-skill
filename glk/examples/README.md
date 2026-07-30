# Example

`appointment-run.yaml` shows two independent entry GO nodes activating together,
one join waiting on both D2 verdicts, and direct successor activation without an
intermediate scheduling queue. Every edge also demonstrates the 2.4.0
producer-to-consumer evidence bindings used by causal slicing.
