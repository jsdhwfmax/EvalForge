"""Serialize synthetic data using the installed, pinned DeepEval model classes.

Run separately with deepeval==3.8.1 and deepeval==4.2.2. No model is created,
evaluate() is never called, and an audit hook blocks outbound connections.
"""

import json
import os
import sys
from importlib.metadata import version
from pathlib import Path


def _block_network(event, args):
    if event in {"socket.connect", "socket.getaddrinfo"}:
        raise RuntimeError("Fixture generation must remain offline")


def main():
    producer_version = version("deepeval")
    if producer_version not in {"3.8.1", "4.2.2"}:
        raise SystemExit("Install deepeval==3.8.1 or deepeval==4.2.2 first")
    os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"
    os.environ["DEEPEVAL_UPDATE_WARNING_OPT_IN"] = "0"
    os.environ["DEEPEVAL_DISABLE_DOTENV"] = "1"
    sys.addaudithook(_block_network)

    from deepeval.evaluate.types import EvaluationResult, TestResult
    from deepeval.test_run.api import MetricData

    legacy = producer_version == "3.8.1"
    results = []
    for index, (relevancy, hallucination) in enumerate([(0.9, 0.1), (0.6, 0.8), (0.8, 0.2)]):
        metadata_field = "additional_metadata" if legacy else "metadata"
        score = hallucination if legacy else 1 - hallucination
        results.append(
            TestResult(
                name="must-not-leak-test-name-%s" % index,
                success=index != 1,
                conversational=False,
                input="must-not-leak-prompt",
                actual_output="must-not-leak-output",
                expected_output="must-not-leak-expected-output",
                context=["must-not-leak-context"],
                retrieval_context=["must-not-leak-retrieval-context"],
                metrics_data=[
                    MetricData(
                        name="Answer Relevancy",
                        score=relevancy,
                        threshold=0.5,
                        success=True,
                        reason="must-not-leak-reason",
                        evaluationModel="must-not-leak-model",
                        verboseLogs="must-not-leak-logs",
                    ),
                    MetricData(
                        name="Hallucination",
                        score=score,
                        threshold=0.5,
                        success=index != 1,
                        reason="must-not-leak-reason",
                    ),
                    MetricData(
                        name="must-not-leak-custom-metric-name",
                        score=0.7,
                        threshold=0.5,
                        success=True,
                    ),
                ],
                **{metadata_field: {"secret": "must-not-leak-metadata"}},
            )
        )
    result = EvaluationResult(
        test_results=results,
        confident_link="https://example.invalid/must-not-leak-confident-link",
        test_run_id="must-not-leak-run-id",
    )
    destination = Path(__file__).parent / ("evaluation-result-%s.json" % producer_version)
    destination.write_text(
        json.dumps(result.model_dump(mode="json", by_alias=False), indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print("Wrote %s using DeepEval %s model classes" % (destination.name, producer_version))


if __name__ == "__main__":
    main()
