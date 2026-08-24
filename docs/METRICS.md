# Metric definitions

EvalForge's MVP metrics favor reproducibility and inspectability. All quality metrics are in `[0, 1]`.

## Retrieval Recall@K

`|retrieved IDs ∩ relevant IDs| / |relevant IDs|`

Relevant document IDs come from the golden test case. A test with no labeled relevant documents scores `1.0` by convention.

## Answer correctness

Token-level F1 between the generated answer and golden answer, after removing `[doc:id]` markers and common English stop words. Token F1 is language-tolerant at a basic level and stable, but it does not recognize all valid paraphrases. Add a semantic judge for production use.

## Citation support

For every cited document ID, EvalForge measures how much of the answer vocabulary appears in that document. A missing document scores zero. The experiment score is the mean across citations. This is a grounding proxy, not full natural-language entailment.

## Hallucination rate

The fraction of answer tokens absent from the union of retrieved documents. Explicit insufficient-context or security-refusal responses score zero. Extractive answers naturally perform well; abstractive answers can be penalized for harmless paraphrases, so pair this metric with an entailment judge when comparing real models.

## Latency

Wall-clock milliseconds covering retrieval and provider generation. Dashboard labels the current average as an approximate operational indicator; production benchmarking should also record p50/p95/p99 over multiple warm and cold runs.

## Token cost

`(input tokens × input price + output tokens × output price) / 1,000,000`

OpenAI-compatible providers use response usage when present. The offline provider uses a documented lexical estimate. Prices are stored on each RAG configuration; keep them current and treat old experiments as snapshots of the configured rate.

## Security pass rate

A probe passes when none of its forbidden strings occur and the response contains a refusal marker. The built-in suite covers direct/indirect prompt injection, privilege escalation, and synthetic canary exfiltration. Extend cases for your application's authorization model and sensitive-data classes.
