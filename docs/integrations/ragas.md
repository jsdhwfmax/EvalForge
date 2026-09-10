# Import Ragas scores into a CI gate

EvalForge imports the JSON records produced by an existing
`EvaluationResult.to_pandas().to_json(orient="records")` export. The adapter runs
locally and needs neither Ragas nor pandas installed. It does not call a model.

## Export from your evaluation environment

After your Ragas evaluation has finished, save its per-sample table:

```python
from importlib.metadata import version

result.to_pandas().to_json("ragas-results.json", orient="records")
print(version("ragas"))  # Supply this actual version to the importer.
```

This export contains both sample content and score columns. It has no producer
version or dataset identity. Keep the raw file in your evaluation environment;
the imported artifact contains only the selected aggregate scores, sample count,
and explicit provenance. Review artifact names and provenance before sharing.

## Run the included example

From an EvalForge checkout with the CLI installed:

```bash
evalforge import ragas tests/fixtures/ragas/evaluation-result-records.json \
  --producer-version 0.2.12 \
  --metric faithfulness \
  --metric answer_relevancy \
  --source-revision example-revision \
  --dataset-fingerprint synthetic-ragas-fixture-v1 \
  --output artifacts/ragas.json

evalforge gate artifacts/ragas.json \
  --policy examples/ragas_policy.json \
  --json artifacts/ragas-gate.json \
  --junit artifacts/ragas-gate.xml \
  --sarif artifacts/ragas-gate.sarif
```

The fixture has two synthetic samples: mean `faithfulness` is `0.75` and mean
`answer_relevancy` is `0.9`. The example policy passes. Its thresholds and minimum
of two samples demonstrate the workflow; set thresholds and a useful sample
minimum for your own application before using it for releases.

For your own export, replace the fixture path, version, metric columns, revision,
and fingerprint. The fingerprint should identify the evaluation dataset, not the
whole results file, whose responses and scores change between runs. EvalForge
records the provided fingerprint; it does not verify or derive one from raw data.

## Mapping and failure behavior

| Input | Portable artifact |
| --- | --- |
| Each repeated `--metric COLUMN` | Arithmetic mean under the original column name |
| Number of records | `test_cases`, with unit `count` |
| `--producer-version` | `producer.name = ragas`, with the supplied version |
| Optional `--source-revision` | `run.source_revision` |
| Optional `--dataset-fingerprint` | `metadata.dataset_fingerprint` |

Every selected metric must be a finite JSON number on **every** row. Missing
columns, `null`, booleans, numeric strings, non-finite values, duplicate JSON keys,
non-object rows, and empty exports fail the import. A failed evaluation row is
never silently removed to raise the mean. Fix or rerun the failed evaluation
before exporting again. Unselected columns are not imported or aggregated.

Column selection is mandatory because numeric sample fields are not necessarily
scores. Known dataset field names, such as `response` and `reference`, are
reserved, and `test_cases` is reserved for the actual sample count. Other custom
score columns are supported when explicitly selected.

Selected metrics use unit `score` and direction `neutral`; the gate policy sets
the comparison operator. The adapter does not equate a Ragas metric with a
similarly named EvalForge metric or assume every custom score is a ratio.
Compare results evaluated with the same metric configuration, model, dataset,
and aggregation. The artifact records mapping version `1`, source format
`ragas.evaluation_result.pandas.records`, selected columns, and aggregation
`mean`. It carries no prompts, responses, retrieved contexts, traces, source
metadata, or unselected scores.

## Python API

```python
from pathlib import Path

from evalforge.adapters.ragas import load_ragas_export
from evalforge.artifacts import write_artifact

artifact = load_ragas_export(
    Path("ragas-results.json"),
    producer_version="0.2.12",  # Use the version that produced your result.
    metrics=["faithfulness", "answer_relevancy"],
    source_revision="your-source-revision",
    dataset_fingerprint="your-dataset-fingerprint",
)
write_artifact(Path("artifacts/ragas.json"), artifact)
```

## Supported format and verification

This adapter accepts a JSON **array of records**, not a Python `repr(result)`,
JSONL, CSV, pandas' default column-oriented JSON, or a Ragas experiment/backend
export. Those formats have different contracts and are rejected rather than
guessed. Producer version is caller-supplied provenance because records JSON
does not embed it.

The serialization contract was verified against the
[Ragas 0.2.12 source](https://github.com/vibrantlabsai/ragas/blob/f5bc2b5e7628f5c68d824e085c4edc17840080b1/src/ragas/dataset_schema.py)
and [pandas records JSON documentation](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_json.html).
See [fixture provenance](../../tests/fixtures/ragas/README.md) for the exact
verification method and its limits. Compatibility with other versions depends
on preserving this same export shape; it is not a claim of exhaustive SDK
version testing.
