# Put evaluation evidence into CI

Install the gate with `pip install evalforge-ci`. It needs neither a model key
nor the Ragas, DeepEval, dashboard, or database dependencies. Run your evaluator
in its own environment, export its results, then import the documented format.

## Reproduce a misleading green check

The files in `examples/strict-comparison/` contain synthetic scores, not a model
benchmark. Both candidates improve the numerical score. The second candidate
changes the dataset, so its improvement cannot establish a regression result.

```bash
evalforge gate examples/strict-comparison/candidate.json \
  --baseline examples/strict-comparison/baseline.json \
  --policy examples/strict-comparison/policy.json \
  --markdown build/summary.md --json build/report.json
# Exit 0: comparable evidence and passing scores.

evalforge gate examples/strict-comparison/changed-dataset.json \
  --baseline examples/strict-comparison/baseline.json \
  --policy examples/strict-comparison/policy.json \
  --markdown build/blocked.md --json build/blocked.json
# Exit 1: both checks report a dataset_fingerprint mismatch, despite quality=0.99.
```

Strict comparison is opt-in. Existing flat JSON summaries keep working with
existing policies. Add a `comparison` object to a reviewed policy:

```json
{
  "require_same_dataset": true,
  "require_same_producer": true,
  "require_same_metric_version": true
}
```

Each enabled requirement needs a baseline, even for an absolute-only policy.
`dataset_fingerprint` and `metric_version` must be non-empty strings in both
artifacts' `metadata`. The producer requirement compares both name and exact
version and rejects `unknown` versions. Missing or mismatched identity fails
every check as an error, including checks marked as advisory warnings.

Choose fingerprints from the actual, canonicalized dataset and metric setup.
These are producer declarations: EvalForge cannot verify that an evaluator
truthfully labeled the data or that two judge executions are scientifically
equivalent. Reset a baseline deliberately when its measurement definition changes.

## Keep reports when the gate fails

This complete workflow assumes your repository commits a trusted baseline and
policy, and its evaluation step produces `build/candidate.json`. Replace that
step with the evaluator command used by your project. Avoid loading secrets or
running untrusted pull-request code in a privileged `pull_request_target` job.

```yaml
name: Evaluation gate
on: [pull_request]
permissions:
  contents: read
jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
      - name: Run your evaluator
        run: python scripts/evaluate.py --output build/candidate.json
      - uses: jsdhwfmax/EvalForge@v0.4.0
        id: evalforge
        with:
          candidate: build/candidate.json
          baseline: evaluation/baseline.json
          policy: evaluation/policy.json
      - name: Preserve gate evidence
        if: always()
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
        with:
          name: evalforge-evidence
          path: |
            evalforge-report.json
            evalforge-junit.xml
            evalforge.sarif
            evalforge-summary.md
          if-no-files-found: warn
```

The Action preserves the CLI failure exit code and appends the Markdown report
to the GitHub job summary for both passing and blocked gates. Set `job-summary:
"false"` to disable the summary. `steps.evalforge.outputs.exit-code` exposes the
gate status for later steps using `if: always()`. Exit 2 means invalid input;
no evaluation report is promised in that case. Pin EvalForge's full release
commit SHA when adopting it in a production workflow.

## Audit a decision

JSON, JUnit, SARIF, and Markdown carry the same evidence identities. The JSON
`evidence` object includes producer name/version, source revision, and SHA-256
digests of the normalized candidate, baseline, and policy. Artifact digests use
`model_dump(mode="json", by_alias=True, exclude_none=True)`; policy digests use
`model_dump(mode="json", by_alias=True)` including defaults. Both use sorted
JSON keys, compact separators, UTF-8, `ensure_ascii=False`, and no non-finite
numbers (`evalforge.canonical-json.v1`). Whitespace and key order in the original
file do not change the digest. Metric values normalize to floats.

Digests identify inputs; they are not cryptographic signatures or proof of who
created an artifact. Keep the artifacts and policy with the report to reproduce
the decision. The gate reports do not copy arbitrary artifact metadata.

## Evaluator contracts

- [promptfoo schema-v3 mapping](INTEROPERABILITY.md#promptfoo-adapter)
- [Ragas selected score columns](integrations/ragas.md)
- [DeepEval version-aware metric mapping](integrations/deepeval.md)

The fixtures demonstrate format compatibility with synthetic data. They are not
evidence of downstream adoption, model quality, or independently measured usage.
