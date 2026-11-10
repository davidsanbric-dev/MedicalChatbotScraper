.PHONY: help install test check-db run docker-build docker-run

# Load variables from .env (POSTGRES_*, DATABASE_URL, ...)
ifneq (,$(wildcard .env))
include .env
export
endif

# Persistence: store raw data in Postgres by default. Set JSON=1 to write
# JSON files into ./scraped instead (e.g. make run JSON=1).
ifndef JSON
PERSIST_FLAG := --database
endif

help:
	@echo "Available targets:"
	@echo "  install      Install Python dependencies with uv"
	@echo "  test         Run the unit tests (offline, no database needed)"
	@echo "  check-db     Verify the shared Postgres (medical_conditions_api stack)"
	@echo "               is reachable on localhost"
	@echo "  run          Run the scraper locally against the shared Postgres"
	@echo "               on localhost (e.g. make run ARGS='--condition acne')"
	@echo "               Persists to Postgres by default; set JSON=1 to write"
	@echo "               JSON files into ./scraped instead (e.g. make run JSON=1)"
	@echo "  docker-build Build the scraper Docker image"
	@echo "  docker-run   Run the scraper in Docker against the host's Postgres"
	@echo "               (e.g. make docker-run ARGS='--condition acne')"
	@echo "               Persists to Postgres by default; set JSON=1 for JSON files"

install:
	uv sync

test:
	uv run pytest

# Verify the shared Postgres from the medical_conditions_api stack is
# up and reachable on localhost:$(POSTGRES_PORT).
check-db:
	@uv run python -c "import psycopg2; psycopg2.connect(host='localhost', port=$(POSTGRES_PORT), user='$(POSTGRES_USER)', password='$(POSTGRES_PASSWORD)', dbname='$(POSTGRES_DB)').close()" 2>/dev/null \
		&& echo "Postgres reachable on localhost:$(POSTGRES_PORT)" \
		|| (echo "Postgres is not reachable on localhost:$(POSTGRES_PORT)."; \
		    echo "Start it from medical_conditions_api: make db-up"; exit 1)

# Run locally (outside Docker), against the Postgres exposed on
# localhost:$(POSTGRES_PORT) by the medical_conditions_api stack.
run: check-db
	DATABASE_URL=postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_PORT)/$(POSTGRES_DB) \
		uv run python main.py $(PERSIST_FLAG) $(ARGS)

docker-build:
	docker compose build

docker-run:
	docker compose run --rm scraper uv run python main.py $(PERSIST_FLAG) $(ARGS)
