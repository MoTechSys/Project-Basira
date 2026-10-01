# RUNBOOK — تشغيل بصيرة في بيئة بديلة من الصفر (الشروط، البند 13/5 و10)

## A) بـ Docker (الموصى به للمحكّمين) — بلا مفاتيح
```bash
git clone <repo> && cd <repo>
docker build -t basira .                 # يجلب المصادر، يبني الفهرس، يكتب snapshot (≈10 دقائق أول مرة)
docker run --rm -p 8000:8000 basira      # LLM_PROVIDER=mock افتراضيًا: الأداة تعمل كاملة بالقواعد الحتمية
open http://localhost:8000               # الواجهة + API على نفس المنفذ
curl -s localhost:8000/health | jq .boot,.boot_seconds,.index_sha256
```
تشغيل مع مزوّد LLM (اختياري): `-e LLM_PROVIDER=openai-compatible -e OPENAI_BASE_URL=… -e OPENAI_API_KEY=…` — بدونه كل شيء يعمل عدا الاقتباسات الضمنية.

## B) بدون Docker
```bash
# backend
cd backend && python3.12 -m venv .venv && . .venv/bin/activate && pip install -e .
cd .. && python corpus/fetch.py && python corpus/build_index.py          # أو make fetch index
PYTHONPATH=backend python -c "from pathlib import Path; from app.snapshot import load_or_build; load_or_build(Path('corpus/index'))"
PYTHONPATH=backend uvicorn app.main:app --port 8000
# frontend (dev)
cd frontend && npm ci && VITE_API_BASE=http://localhost:8000 npm run dev
```

## C) التحقق
```bash
cd backend && pytest -q && ruff check app tests && mypy app
python eval/run_eval.py --index corpus/index --repeats 3 --false-alarm 500 --fail-on-unsafe   # 150/150, FA 0/500
cd frontend && npm test && npm run build
```

## D) ما لا نسلّمه (مسموح وفق البند 13/5)
مفاتيح سرية، حسابات، بيانات مستفيدين حقيقية — لا توجد أصلًا؛ المشروع لا يخزّن أي نص.
