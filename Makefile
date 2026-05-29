.PHONY: help install up down logs build migrate test api consumer fmt

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:
	uv pip install -r requirements.txt

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f

migrate:
	docker compose run --rm migrate

test:
	uv run python -m pytest tests/ -q

api:
	uv run uvicorn src.main:app --reload

consumer:
	uv run python -m src.consumer_main
