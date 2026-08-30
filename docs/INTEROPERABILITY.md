# Portable evaluation evidence and policy gates

EvalForge separates **measurement** from **release policy**. A model evaluator, RAG benchmark, red-team suite, or custom script measures the system. EvalForge carries the resulting metrics in a small versioned artifact, compares releases, applies explicit policy, and emits reports for CI systems.

This boundary is useful because teams should be able to change an evaluator without rewriting every release check or losing historical evidence.

## Evaluation artifact v1

The normative machine-readable schema is [`schemas/evaluation-artifact-v1.schema.json`](../schemas/evaluation-artifact-v1.schema.json).

```json
{
  "$schema": "https://raw.githubusercontent.com/jsdhwfmax/EvalForge/main/schemas/evaluation-artifact-v1.schema.json",
  "schema_version": "1.0",
  "producer": {"name": "my-evaluator", "version": "3.2.1"},
  "run": {"id": "release-42", "source_revision": "2f43a9e"},
  "metrics": {
    "faithfulness": {"value": 0.91, "unit": "ratio", "direction": "higher"},
    "latency_ms": {"value": 420, "unit": "ms", "direction": "lower"}
  },
  "metadata": {"dataset": "support-golden-v7"}
}
```

Metric names are intentionally open. Unknown metrics remain valid. A producer should use stable names and document changes in meaning; changing a metric definition without changing its name makes baselines misleading.

For incremental adoption, `evalforge gate` also accepts a flat JSON object of numeric metrics or an object with a `summary` field. EvalForge assigns known units and directions where possible and treats unknown values as neutral scores.

## Gate policy v1

The normative schema is [`schemas/gate-policy-v1.schema.json`](../schemas/gate-policy-v1.schema.json).

Each check names a metric, comparison, threshold, and severity:

- `gte` / `lte` compare the candidate value to an absolute threshold.
- `delta_gte` / `delta_lte` compare `candidate - baseline` to a permitted change.
- `error` failures block the gate.
- `warning` failures remain visible without blocking the gate.

Missing candidate metrics, missing baseline metrics, and delta checks without a baseline are configuration errors and always fail. EvalForge does not silently skip a release requirement.

## Reports

- JSON preserves every evaluated value and message for automation.
- JUnit represents each policy check as a test case for test-report viewers.
- SARIF represents failed and warning checks as static-analysis results for code scanning interfaces.

SARIF results are run-level findings and intentionally omit a fabricated source location. Consumers should link the report to the evaluation artifact and source revision.

## Compatibility rules

Schema version `1.0` follows these rules:

1. New optional fields may be added in a minor EvalForge release.
2. Removing a field, changing its type, or changing gate semantics requires a new schema version.
3. Readers reject unknown top-level fields in canonical artifacts and policies to expose typos early.
4. Flat-summary compatibility is convenience input, not a replacement for the canonical artifact.
5. Metric semantics belong to the producer; EvalForge evaluates the declared numeric evidence and never implies scientific validity.

Open an issue before proposing a schema change. Include a real producer/consumer use case and a migration example.
