.PHONY: install test lint gate-demo package run dashboard demo docker

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e ".[rag,dashboard,dev]"

test:
	pytest --cov=evalforge --cov-report=term-missing

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

run:
	uvicorn evalforge.api:app --reload

dashboard:
	streamlit run dashboard/app.py

demo:
	evalforge seed
	evalforge run baseline_top1 --name "Baseline"
	evalforge run hybrid_top3 --name "Candidate"

docker:
	docker compose up --build
