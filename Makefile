PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
STREAMLIT ?= .venv/bin/streamlit
PYTHONPATH := src

.PHONY: install install-ui test demo ui docker-build docker-up docker-down docker-logs analyze-case search audit clean clean-cache clean-cases clean-demo-reports

install:
	$(PIP) install -r requirements.txt

install-ui:
	$(PIP) install -r requirements-ui.txt

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest

demo:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m vitalsignal.demo_cli

ui:
	PYTHONPATH=$(PYTHONPATH) $(STREAMLIT) run src/vitalsignal/app/streamlit_app.py

docker-build:
	docker compose build

docker-up:
	docker compose up

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f vitalsignal-ui

analyze-case:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m vitalsignal.main $(CASE_ID)

search:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m vitalsignal.search_cli --start-case-id $(START_CASE_ID) --end-case-id $(END_CASE_ID) --anomaly $(ANOMALY)

audit:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m vitalsignal.score_audit_cli --start-case-id $(START_CASE_ID) --end-case-id $(END_CASE_ID) --output reports/score_audit_$(START_CASE_ID)_$(END_CASE_ID).json

clean: clean-cache

clean-cache:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -prune -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete

clean-cases:
	rm -rf cases/

clean-demo-reports:
	rm -f reports/case_*.json reports/case_*.md reports/search_*.json reports/search_*.csv
