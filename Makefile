.PHONY: help install test lint fmt dev clean fetch snapshot eval

help:
	@echo "Basira — available targets:"
	@echo ""
	@echo "  make install     Install backend + frontend dependencies"
	@echo "  make test        Run all tests (backend + frontend)"
	@echo "  make lint        Lint all code"
	@echo "  make fmt         Format all code"
	@echo "  make dev         Run backend + frontend in development mode"
	@echo "  make fetch       Download Quran + Hadith sources"
	@echo "  make snapshot    Build fast-boot snapshot"
	@echo "  make eval        Run evaluation suite"
	@echo "  make clean       Remove generated files"

install:
	@echo "Installing backend..."
	cd backend && pip install -e ".[dev]"
	@echo "Installing frontend..."
	cd frontend && npm install

test:
	cd backend && pytest -q
	cd frontend && npm test -- --run

lint:
	cd backend && ruff check . && mypy app/
	cd frontend && npm run lint

fmt:
	cd backend && ruff format .
	cd frontend && npm run format

dev:
	@echo "Run backend:  make -C backend serve"
	@echo "Run frontend: make -C frontend dev"

fetch:
	cd corpus && python fetch.py

snapshot:
	cd corpus && python build_index.py

eval:
	cd eval && python run_eval.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.coverage backend/htmlcov
	rm -rf frontend/dist frontend/node_modules/.vite
