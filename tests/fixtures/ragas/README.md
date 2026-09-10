# Ragas fixture provenance

`evaluation-result-records.json` contains invented sample content and scores.
It represents this specific serialization of an existing Ragas result:

```python
result.to_pandas().to_json(orient="records", indent=2)
```

The export path was verified against Ragas **0.2.12**, upstream commit
[`f5bc2b5e7628f5c68d824e085c4edc17840080b1`](https://github.com/vibrantlabsai/ragas/blob/f5bc2b5e7628f5c68d824e085c4edc17840080b1/src/ragas/dataset_schema.py).
`EvaluationResult.to_pandas()` concatenates dataset fields with per-row scores.
The [pandas records orientation](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_json.html)
serializes that table as an array of row objects, and converts missing numeric
values to JSON `null`.

During fixture preparation, the upstream `EvaluationResult.to_pandas` method
body was extracted with Python's AST parser and executed with pandas **2.3.3**,
the synthetic score dictionaries, and a small dataset shim exposing `__len__`
and `to_pandas`. Its records JSON was checked for semantic equality with this
fixture and then saved here. The full Ragas package was not installed or run;
no model, paid API, or real user data was used. This verifies the serialization
path, not model scoring or every Ragas release.

To reproduce in an environment that already has Ragas 0.2.12 and pandas:

```python
import json
from pathlib import Path

from ragas import EvaluationDataset
from ragas.dataset_schema import EvaluationResult

path = Path("tests/fixtures/ragas/evaluation-result-records.json")
rows = json.loads(path.read_text())
columns = {"faithfulness", "answer_relevancy", "answer_correctness"}
samples = [{k: v for k, v in row.items() if k not in columns} for row in rows]
scores = [{k: v for k, v in row.items() if k in columns} for row in rows]
result = EvaluationResult(scores=scores, dataset=EvaluationDataset.from_list(samples))
assert json.loads(result.to_pandas().to_json(orient="records")) == rows
```

The reproduction snippet constructs a result from synthetic scores; it does not
run an evaluation. Ragas is Apache-2.0 licensed; its
[license](https://github.com/vibrantlabsai/ragas/blob/f5bc2b5e7628f5c68d824e085c4edc17840080b1/LICENSE)
is available upstream. The fixture's content was authored for EvalForge.
