import asyncio, os, time, httpx, collections
A_URL = os.environ["ANTHROPIC_BASE_URL"] + "/v1/messages"
O_URL = os.environ["OPENAI_BASE_URL"] + "/chat/completions"
A_H = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"}
O_H = {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}
async def call(c, i, model):
    t=time.perf_counter()
    if model.startswith("claude"):
        r = await c.post(A_URL, headers=A_H, json={"model": model, "max_tokens": 20, "messages":[{"role":"user","content":f"Say OK {i}"}]})
    else:
        r = await c.post(O_URL, headers=O_H, json={"model": model, "messages":[{"role":"user","content":f"Say OK {i}"}]})
    body = r.text[:160].replace("\n"," ")
    return model, r.status_code, round(time.perf_counter()-t,2), body
async def main(n_per, models):
    async with httpx.AsyncClient(timeout=180) as c:
        t0=time.perf_counter()
        res = await asyncio.gather(*[call(c, i, m) for m in models for i in range(n_per)])
        wall=time.perf_counter()-t0
    print(f"\n### {n_per} concurrent per model × {len(models)} models = {len(res)} calls, wall {wall:.1f}s")
    for m in models:
        codes = collections.Counter(r[1] for r in res if r[0]==m)
        print(f"  {m:20} {dict(codes)}")
    for r in res:
        if r[1]!=200: print("   ", r[0], r[1], r[3]); break
asyncio.run(main(8, ["claude-sonnet-4-5","claude-opus-4-6","gpt-5.2","deep-seek-v4-pro"]))
asyncio.run(main(16, ["claude-sonnet-4-5","gpt-5.2"]))
