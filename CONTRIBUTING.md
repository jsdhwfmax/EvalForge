# Contributing

Thanks for helping make RAG quality measurable.

1. Open an issue for substantial behavior or architecture changes.
2. Create a focused branch and add tests for new behavior.
3. Run `make lint` and `make test` locally.
4. Keep metrics deterministic or document nondeterminism and confidence intervals.
5. Never include customer data, real credentials, or private prompts in fixtures.

Pull requests should explain the user problem, implementation, verification evidence, and any metric-compatibility impact. Changes to a metric definition should update `docs/METRICS.md` and include before/after fixtures.

Changes to the portable artifact or gate policy must also update the matching JSON Schema, `docs/INTEROPERABILITY.md`, and compatibility tests. New evaluator integrations should be backed by a sanitized upstream fixture rather than an invented output shape.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[rag,dashboard,dev]"
evalforge seed
pytest
```

The project targets Python 3.9 and 3.12. Please keep new code compatible with both.
