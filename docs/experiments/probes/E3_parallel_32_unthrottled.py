"""Measure real parallel fan-out capacity across model families (no hallucination: timings are measured)."""
import asyncio, json, os, time
import httpx

A_URL = os.environ["ANTHROPIC_BASE_URL"] + "/v1/messages"
O_URL = os.environ["OPENAI_BASE_URL"] + "/chat/completions"
A_H = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"}
O_H = {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}

PROMPT = "You are worker #{i}. Return ONLY a JSON object {{\"worker\": {i}, \"square\": <{i} squared>}}."

async def call(client, i, model):
    t = time.perf_counter()
    try:
        if model.startswith("claude"):
            r = await client.post(A_URL, headers=A_H, json={"model": model, "max_tokens": 60,
                 "messages": [{"role": "user", "content": PROMPT.format(i=i)}]})
            txt = r.json()["content"][0]["text"]
        else:
            r = await client.post(O_URL, headers=O_H, json={"model": model,
                 "messages": [{"role": "user", "content": PROMPT.format(i=i)}]})
            txt = r.json()["choices"][0]["message"]["content"]
        ok = f'"square": {i*i}' in txt.replace(" ", "").replace('"square":', '"square": ') or str(i*i) in txt
        return (model, i, ok, round(time.perf_counter() - t, 2), None)
    except Exception as e:
        return (model, i, False, round(time.perf_counter() - t, 2), str(e)[:80])

async def main():
    plan = {"claude-sonnet-4-5": 8, "claude-opus-4-6": 4, "gpt-5.2": 6, "gpt-5-mini": 6, "deep-seek-v4-pro": 4, "glm-5p3": 4}
    tasks, i = [], 0
    async with httpx.AsyncClient(timeout=180) as c:
        for model, n in plan.items():
            for _ in range(n):
                i += 1; tasks.append(call(c, i, model))
        t0 = time.perf_counter()
        res = await asyncio.gather(*tasks)
        wall = time.perf_counter() - t0
    print(f"{len(res)} workers launched concurrently — wall clock {wall:.1f}s")
    print(f"{'model':22} {'ok':>5} {'fail':>5} {'avg s':>7} {'max s':>7}")
    for model in plan:
        rs = [r for r in res if r[0] == model]
        ok = sum(r[2] for r in rs); lat = [r[3] for r in rs]
        print(f"{model:22} {ok:>5} {len(rs)-ok:>5} {sum(lat)/len(lat):>7.2f} {max(lat):>7.2f}")
    errs = [r for r in res if r[4]]
    for e in errs: print("  ERR", e[0], e[1], e[4])
    print("sequential-equivalent ≈", round(sum(r[3] for r in res), 1), "s  → speedup ×", round(sum(r[3] for r in res)/wall, 1))

asyncio.run(main())
