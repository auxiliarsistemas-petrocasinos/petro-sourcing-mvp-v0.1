.PHONY: setup sync dev run health test lint clean

setup:
	uv python install 3.12
	uv sync
	@test -f .env || cp .env.example .env
	@echo "Listo. Edita .env si aún no agregaste OPENAI_API_KEY."

sync:
	uv sync

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port $${PORT:-8000}

run: dev

health:
	curl -fsS http://127.0.0.1:8000/api/health && echo

test:
	uv run pytest

lint:
	uv run ruff check .

clean:
	rm -rf .venv .pytest_cache .ruff_cache __pycache__ app/__pycache__
