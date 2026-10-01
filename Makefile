.PHONY: bootstrap fetch index lint test gates smoke fixture serve
PY=backend/.venv/bin/python
bootstrap: ; bash scripts/bootstrap.sh
fetch:     ; python3 corpus/fetch.py
index:     ; $(PY) corpus/build_index.py
lint:      ; cd backend && .venv/bin/ruff check app tests && .venv/bin/mypy
test:      ; cd backend && .venv/bin/pytest -q
gates: lint test
smoke:     ; $(PY) scripts/smoke.py
fixture:   ; $(PY) corpus/build_fixture.py
serve:     ; cd backend \&\& .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
