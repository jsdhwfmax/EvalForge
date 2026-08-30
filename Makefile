.PHONY: install test lint gate-demo package release-check run dashboard demo docker

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e ".[rag,dashboard,dev]"

test:
	pytest --cov=evalforge --cov-report=term-missing --cov-fail-under=85

lint:
	ruff check .
	mypy src/evalforge

gate-demo:
	mkdir -p build
	$(PYTHON) -m evalforge.cli gate examples/candidate_summary.json \
		--policy examples/quality_policy.json \
		--baseline examples/baseline_summary.json \
		--json build/evalforge-report.json \
		--junit build/evalforge-junit.xml \
		--sarif build/evalforge.sarif

package:
	$(PYTHON) -m build

release-check: package
	$(PYTHON) -m twine check dist/*.whl dist/*.tar.gz

run:
	uvicorn evalforge.api:app --reload

dashboard:
	streamlit run dashboard/app.py

demo:
	evalforge seed
	evalforge run baseline_top1 --name "Baseline"
	evalforge run hybrid_top3 --name "Candidate"
	evalforge check hybrid_top3 --name "Release candidate" --report-dir artifacts

docker:
	docker compose up --build
