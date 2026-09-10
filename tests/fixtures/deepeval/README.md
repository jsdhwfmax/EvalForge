# DeepEval fixture provenance

These fixtures contain synthetic scores and text authored for EvalForge. They
were serialized with the **actual installed DeepEval model classes** using
`EvaluationResult.model_dump(mode="json", by_alias=False)`. They are not measured
LLM evaluation results and do not establish model quality or integration adoption.

| Fixture | Installed package | Upstream tag | Pinned commit |
| --- | --- | --- | --- |
| `evaluation-result-3.8.1.json` | `deepeval==3.8.1` | `v3.8.1` | `fc268fa3fc04e0f5ebb25db3631788913c02b38a` |
| `evaluation-result-4.2.2.json` | `deepeval==4.2.2` | `python-v4.2.2` | `f94d940c1e5afc4b280420fe73fe17d146274018` |

Verified on 2026-09-10 against the upstream sources and PyPI packages. The
`generate.py` script constructs `TestResult` and `MetricData`, then serializes the
containing `EvaluationResult`. It disables dotenv loading, telemetry, and update
checks and installs a Python audit hook that blocks DNS/connection attempts. It
does not call `evaluate()`, instantiate a metric/judge, or send a model request.
Package installation requires network access; fixture generation does not.

Reproduce in a disposable environment, running once per supported version:

```bash
python -m venv /tmp/evalforge-deepeval-fixtures
/tmp/evalforge-deepeval-fixtures/bin/python -m pip install 'deepeval==3.8.1'
/tmp/evalforge-deepeval-fixtures/bin/python tests/fixtures/deepeval/generate.py
/tmp/evalforge-deepeval-fixtures/bin/python -m pip install 'deepeval==4.2.2'
/tmp/evalforge-deepeval-fixtures/bin/python tests/fixtures/deepeval/generate.py
```

The generator intentionally puts `must-not-leak` markers in raw prompts,
responses, context, metric reasons/logs/model identifiers, custom metric names,
test names, run identifiers, links, and metadata. Tests require these markers to
be absent from the imported artifact.

Source contracts:

- [3.8.1 EvaluationResult and TestResult](https://github.com/confident-ai/deepeval/blob/fc268fa3fc04e0f5ebb25db3631788913c02b38a/deepeval/evaluate/types.py)
- [3.8.1 MetricData](https://github.com/confident-ai/deepeval/blob/fc268fa3fc04e0f5ebb25db3631788913c02b38a/deepeval/tracing/api.py)
- [4.2.2 EvaluationResult and TestResult](https://github.com/confident-ai/deepeval/blob/f94d940c1e5afc4b280420fe73fe17d146274018/deepeval/evaluate/types.py)
- [4.2.2 MetricData](https://github.com/confident-ai/deepeval/blob/f94d940c1e5afc4b280420fe73fe17d146274018/deepeval/tracing/api.py)
- [3.8.1 Hallucination score and success rule](https://github.com/confident-ai/deepeval/blob/fc268fa3fc04e0f5ebb25db3631788913c02b38a/deepeval/metrics/hallucination/hallucination.py)
- [4.2.2 Hallucination score](https://github.com/confident-ai/deepeval/blob/f94d940c1e5afc4b280420fe73fe17d146274018/deepeval/metrics/hallucination/hallucination.py)
- [4.2.2 common success rule](https://github.com/confident-ai/deepeval/blob/f94d940c1e5afc4b280420fe73fe17d146274018/deepeval/metrics/base_metric.py)

DeepEval is Apache-2.0 licensed; see the
[upstream license](https://github.com/confident-ai/deepeval/blob/f94d940c1e5afc4b280420fe73fe17d146274018/LICENSE.md).
The generator and synthetic data were written for EvalForge; no upstream model
implementation is vendored.
