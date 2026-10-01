.PHONY: bootstrap fetch index lint test gates smoke fixture serve eval eval-full
PY=backend/.venv/bin/python
bootstrap: ; bash scripts/bootstrap.sh
fetch:     ; python3 corpus/fetch.py
index:     ; $(PY) corpus/build_index.py
lint:      ; cd backend && .venv/bin/ruff check app tests && .venv/bin/mypy && .venv/bin/ruff check --config pyproject.toml ../corpus ../eval ../scripts/smoke.py
test:      ; cd backend && .venv/bin/pytest -q
gates: lint test
smoke:     ; $(PY) scripts/smoke.py
fixture:   ; $(PY) corpus/build_fixture.py
serve:     ; bash scripts/serve.sh
eval:      ; $(PY) eval/run_eval.py --repeats 3 --fail-on-unsafe
eval-full: ; $(PY) eval/run_eval.py --index corpus/index --repeats 3 --false-alarm 500 --fail-on-unsafe
scholar:   ; $(PY) eval/scholar_probe.py $${BASIRA_URL:-http://localhost:8000}
