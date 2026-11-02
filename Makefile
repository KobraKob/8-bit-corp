.PHONY: dev test lint install

install:
	python -m pip install -e backend
	cd frontend && pnpm install

dev-backend:
	python -m uvicorn app.main:app --app-dir backend --reload --port 8000

dev-frontend:
	cd frontend && pnpm dev

test:
	pytest backend/tests

lint:
	python -m pytest --version
