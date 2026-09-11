.PHONY: setup up down test docs dashboard lint dbt e2e migrate validate-data import-data

PYTHON ?= python3.11

setup:
	cp -n .env.example .env || true
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -r requirements.txt

up:
	docker compose up --build

down:
	docker compose down

test:
	.venv/bin/pytest tests --cov=src --cov-report=term-missing

lint:
	.venv/bin/flake8 src tests --max-line-length=120 --extend-ignore=E203

dashboard:
	.venv/bin/streamlit run src/dashboard/app.py

docs:
	.venv/bin/mkdocs serve -a 127.0.0.1:8000

dbt:
	cd dbt_project && ../.venv/bin/dbt build --profiles-dir .

e2e:
	bash scripts/e2e_check.sh

migrate:
	docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' < sql/migrations/002_add_source.sql

validate-data:
	@test -n "$(FILE)" || (echo "Usage: make validate-data FILE=/absolute/path/data.csv" && exit 1)
	docker compose run --rm --no-deps -v "$(abspath $(FILE)):/import/$(notdir $(FILE)):ro" producer \
		python -m src.ingestion.importer --file "/import/$(notdir $(FILE))" --validate-only

import-data: migrate
	@test -n "$(FILE)" || (echo "Usage: make import-data FILE=/absolute/path/data.csv" && exit 1)
	docker compose run --rm --no-deps -v "$(abspath $(FILE)):/import/$(notdir $(FILE)):ro" producer \
		python -m src.ingestion.importer --file "/import/$(notdir $(FILE))"
