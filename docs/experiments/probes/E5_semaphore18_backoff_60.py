import asyncio, os, time, httpx, collections
A_URL = os.environ["ANTHROPIC_BASE_URL"] + "/v1/messages"
A_H = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"}
SEM = asyncio.Semaphore(18)  # safety margin under the 20 hard cap
async def call(c, i, model):
    async with SEM:
        for attempt in range(4):
            r = await c.post(A_URL, headers=A_H, json={"model": model, "max_tokens": 20, "messages":[{"role":"user","content":f"Say OK {i}"}]})
            if r.status_code != 429: return r.status_code, attempt
            await asyncio.sleep(0.5 * 2**attempt)
        return 429, attempt
async def main():
    async with httpx.AsyncClient(timeout=180) as c:
        t0=time.perf_counter()
        res = await asyncio.gather(*[call(c, i, "claude-sonnet-4-5" if i%2 else "claude-opus-4-6") for i in range(60)])
        wall=time.perf_counter()-t0
    print(f"60 tasks through semaphore(18)+backoff: wall {wall:.1f}s")
    print(" status:", dict(collections.Counter(r[0] for r in res)), " retries used:", dict(collections.Counter(r[1] for r in res)))
asyncio.run(main())
