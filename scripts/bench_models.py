"""Benchmark proxy models on Basira's real extraction task (span location). Measures: exact-span
correctness vs rule-engine gold, latency, success. No religious text invented: cases are from eval/cases.yaml."""
import asyncio, json, os, sys, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "backend"))
import httpx
from app.providers.openai_compat import EXTRACT_SYSTEM, _parse_quotes

BASE = os.environ["OPENAI_BASE_URL"].rstrip("/") + "/chat/completions"
KEY = os.environ["GSK_TEST_KEY"]
MODELS = sys.argv[1].split(",")
CASES = [
  ("قال تعالى: ﴿إن الله مع الصابرين﴾ وهذا من أعظم البشارات.", ["إن الله مع الصابرين"]),
  ("قال رسول الله ﷺ: «إنما الأعمال بالنيات» رواه البخاري.", ["إنما الأعمال بالنيات"]),
  ("كتب أحدهم: قل هو HELLO الله أحد، ثم تابع كلامه.", ["قل هو HELLO الله أحد"]),
  ("يُقال: الدين المعاملة، وهو كلام متداول.", ["الدين المعاملة"]),
  ("هذا نص عادي لا يحتوي على أي اقتباس ديني، فقط حديث عن الطقس اليوم.", []),
  ("He wrote: \"Indeed, Allah is with the patient\" and moved on.", ["Indeed, Allah is with the patient"]),
]

def norm(s): return " ".join(s.replace("،",",").split()).strip(" .،\"«»﴿﴾")

async def run(model, text, gold, client):
  body = {"model": model, "temperature": 0, "response_format": {"type":"json_object"},
          "messages":[{"role":"system","content":EXTRACT_SYSTEM},{"role":"user","content":text}]}
  t0=time.perf_counter()
  try:
    r = await client.post(BASE, headers={"Authorization":f"Bearer {KEY}"}, json=body)
    ms=int((time.perf_counter()-t0)*1000)
    if r.status_code!=200: return {"ok":False,"err":f"http {r.status_code}: {r.text[:120]}","ms":ms}
    j=r.json(); content=j["choices"][0]["message"]["content"]
    usage=j.get("usage",{})
    quotes=_parse_quotes(content)
    got=[norm(q.quoted_text) for q in quotes]
    exp=[norm(g) for g in gold]
    exact = got==exp
    verbatim_ok = all(norm(q.quoted_text) in norm(text) or q.quoted_text in text for q in quotes)
    return {"ok":True,"exact":exact,"verbatim":verbatim_ok,"got":got,"ms":ms,"tok":usage.get("total_tokens")}
  except Exception as e:
    return {"ok":False,"err":f"{e.__class__.__name__}: {str(e)[:100]}","ms":int((time.perf_counter()-t0)*1000)}

async def main():
  out={}
  async with httpx.AsyncClient(timeout=90) as client:
    for m in MODELS:
      res=await asyncio.gather(*[run(m,t,g,client) for t,g in CASES])
      ok=[r for r in res if r["ok"]]
      out[m]={"calls":len(res),"ok":len(ok),"exact":sum(r.get("exact",False) for r in ok),
              "verbatim":sum(r.get("verbatim",False) for r in ok),
              "p50_ms":sorted(r["ms"] for r in res)[len(res)//2],"max_ms":max(r["ms"] for r in res),
              "errors":[r["err"] for r in res if not r["ok"]][:2],
              "miss":[(CASES[i][0][:30],r.get("got")) for i,r in enumerate(res) if r["ok"] and not r.get("exact")][:3]}
      print(json.dumps({m:out[m]},ensure_ascii=False)); sys.stdout.flush()
  json.dump(out,open("/tmp/bench/results.json","a"),ensure_ascii=False)
asyncio.run(main())
