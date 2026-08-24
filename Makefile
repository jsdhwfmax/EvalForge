.PHONY: install test lint run dashboard demo docker

install:
	python -m pip install -e ".[dashboard,dev]"

test:
	pytest --cov=evalforge --cov-report=term-missing

lint:
	ruff check .
	mypy src/evalforge

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
