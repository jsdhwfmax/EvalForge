# Import DeepEval evaluation evidence

EvalForge imports a local JSON serialization of DeepEval's `EvaluationResult`
into aggregate evidence for policy gates. DeepEval does not need to be installed
in the environment importing or gating the artifact.

The supported producer versions are **3.8.1 and 4.2.2**, each verified against a
fixed upstream tag and the installed package. Other versions are rejected until
their export shape and metric semantics are verified. The import contract is
`EvaluationResult.model_dump(mode="json", by_alias=False)`, which contains a
`test_results` array with `name`, `success`, `conversational`, and `metrics_data`
on each row. It is not DeepEval's `TestRun`/`.latest_run_full.json` format or a
Confident AI API response. See the pinned
[types for 4.2.2](https://github.com/confident-ai/deepeval/blob/f94d940c1e5afc4b280420fe73fe17d146274018/deepeval/evaluate/types.py)
and [fixture provenance](../../tests/fixtures/deepeval/README.md).

## Export and import

Save the result of an existing evaluation in the environment that ran DeepEval:

```python
import json
from importlib.metadata import version
from pathlib import Path

# result is the EvaluationResult returned by your existing evaluate(...) call.
Path("deepeval-results.json").write_text(
    json.dumps(result.model_dump(mode="json", by_alias=False), allow_nan=False),
    encoding="utf-8",
)
print(version("deepeval"))  # Pass this exact installed version to the importer.
```

The export contains raw evaluation content. Keep it in your evaluation
environment; publish the aggregate artifact if that is the intended evidence.
Importing the export makes no model or network calls:

```bash
evalforge import deepeval deepeval-results.json \
  --producer-version 4.2.2 \
  --source-revision YOUR_GIT_COMMIT \
  --dataset-fingerprint sha256:YOUR_DATASET_DIGEST \
  --metric-version YOUR_JUDGE_AND_METRIC_CONFIG_DIGEST \
  --output deepeval-artifact.json
evalforge gate deepeval-artifact.json --policy examples/deepeval_policy.json
```

`--metric-version` is a caller-supplied identity for the actual judge and metric
configuration, including relevant prompts, parameters, and thresholds. The
adapter mapping version only identifies import code; it is not a substitute for
that configuration identity. Dataset fingerprints and source revisions also come
from explicit arguments, never arbitrary fields in the source export.

Python callers can use the same importer:

```python
from pathlib import Path
from evalforge.adapters.deepeval import load_deepeval_export
from evalforge.artifacts import write_artifact

artifact = load_deepeval_export(
    Path("deepeval-results.json"),
    producer_version="4.2.2",
    source_revision="YOUR_GIT_COMMIT",
    dataset_fingerprint="sha256:YOUR_DATASET_DIGEST",
)
artifact.metadata["metric_version"] = "YOUR_JUDGE_AND_METRIC_CONFIG_DIGEST"
write_artifact(Path("deepeval-artifact.json"), artifact)
```

## Metrics and direction

`test_cases` counts result rows. `deepeval_pass_rate` divides passing rows by
**all** rows. Every exported score is the arithmetic mean over that same complete
suite. The importer uses this fixed allowlist of exact built-in display names:

| DeepEval name | Artifact metric | Direction |
| --- | --- | --- |
| Answer Relevancy | `deepeval_answer_relevancy` | higher |
| Faithfulness | `deepeval_faithfulness` | higher |
| Contextual Precision | `deepeval_contextual_precision` | higher |
| Contextual Recall | `deepeval_contextual_recall` | higher |
| Contextual Relevancy | `deepeval_contextual_relevancy` | higher |
| Tool Correctness | `deepeval_tool_correctness` | higher |
| Task Completion | `deepeval_task_completion` | higher |
| Hallucination (3.8.1) | `deepeval_v3_hallucination` | lower |
| Bias (3.8.1) | `deepeval_v3_bias` | lower |
| Toxicity (3.8.1) | `deepeval_v3_toxicity` | lower |
| Hallucination (4.2.2) | `deepeval_v4_hallucination` | higher |
| Bias (4.2.2) | `deepeval_v4_bias` | higher |
| Toxicity (4.2.2) | `deepeval_v4_toxicity` | higher |

DeepEval's `MetricData` has no direction field. The mapping is derived from the
pinned metric implementations. In 3.8.1, Hallucination measures contradictory
contexts; in 4.2.2 it measures aligned contexts. Bias and Toxicity also reversed
score meaning. These three metrics use separate names across versions so a gate
cannot accidentally reuse a threshold or baseline with the opposite meaning.
Scores are preserved, not inverted by the adapter. Sources:
[3.8.1 Hallucination](https://github.com/confident-ai/deepeval/blob/fc268fa3fc04e0f5ebb25db3631788913c02b38a/deepeval/metrics/hallucination/hallucination.py),
[4.2.2 Hallucination](https://github.com/confident-ai/deepeval/blob/f94d940c1e5afc4b280420fe73fe17d146274018/deepeval/metrics/hallucination/hallucination.py),
[4.2.2 Bias](https://github.com/confident-ai/deepeval/blob/f94d940c1e5afc4b280420fe73fe17d146274018/deepeval/metrics/bias/bias.py),
[4.2.2 Toxicity](https://github.com/confident-ai/deepeval/blob/f94d940c1e5afc4b280420fe73fe17d146274018/deepeval/metrics/toxicity/toxicity.py).

Custom metric names are not copied or converted to slugs. Their verdicts still
participate in the overall pass rate, and their numeric/error fields still must
be valid. An export containing only custom metrics produces sample count and
pass rate. Do not give a custom implementation a built-in display name with
different semantics; this file format cannot authenticate metric code.

## Validation and privacy

Each result must contain the same nonempty metric suite with no duplicate names.
Every score and threshold must be a finite number, and every success value must
be a boolean. Missing/null/non-finite scores, errored metrics, score-only metrics,
flaky metrics, mixed conversation modes, and inconsistent verdicts fail the
import. Built-in scores and thresholds must be in `[0, 1]`, and their verdicts must
match the versioned threshold rule. Custom metric threshold rules are not
inferred. A failed import never produces a partially averaged artifact. The
adapter cannot detect test cases removed before export; set a minimum
`test_cases` gate and compare a trusted dataset fingerprint.

The artifact excludes test names, inputs, outputs, expected outputs, contexts,
turns, reasons, traces, logs, model identifiers, costs, arbitrary metric names,
metadata, Confident AI links, and run IDs from the export. Error messages use
structural positions rather than quoting raw values. Caller-supplied revision,
dataset, and metric-configuration identifiers are retained intentionally.

The example policy targets 4.2.2 and uses illustrative thresholds. Its v4
Hallucination check fails with missing evidence on a 3.8.1 artifact rather than
silently treating the old score as equivalent. The offline fixtures are
synthetic contract tests; they do not demonstrate the quality of an LLM.
