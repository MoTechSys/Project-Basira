import asyncio, os, time, httpx, json
A=os.environ["ANTHROPIC_BASE_URL"]+"/v1/messages"; AH={"x-api-key":os.environ["ANTHROPIC_API_KEY"],"anthropic-version":"2023-06-01"}
O=os.environ["OPENAI_BASE_URL"]+"/chat/completions"; OH={"Authorization":"Bearer "+os.environ["OPENAI_API_KEY"]}
Q="A hadith checker must never output the word 'fabricated'. In ONE sentence, why? Then on a new line write TOKENS_OK."
async def claude(c,m,think):
    body={"model":m,"max_tokens":4000,"messages":[{"role":"user","content":Q}]}
    if think: body["thinking"]={"type":"enabled","budget_tokens":2000}
    t=time.perf_counter(); r=await c.post(A,headers=AH,json=body); d=r.json()
    if r.status_code!=200: return m,("think" if think else "plain"),r.status_code,str(d)[:120],0
    txt=" ".join(b.get("text","") for b in d["content"] if b["type"]=="text"); thought=any(b["type"]=="thinking" for b in d["content"])
    return m,("think" if think else "plain"),200,("THOUGHT " if thought else "")+txt[:90].replace("\n"," "),round(time.perf_counter()-t,1)
async def gpt(c,m,effort):
    body={"model":m,"messages":[{"role":"user","content":Q}]}
    if effort: body["reasoning_effort"]=effort
    t=time.perf_counter(); r=await c.post(O,headers=OH,json=body); d=r.json()
    if r.status_code!=200: return m,effort or "plain",r.status_code,str(d)[:120],0
    u=d.get("usage",{}); rt=u.get("completion_tokens_details",{}).get("reasoning_tokens",0)
    return m,effort or "plain",200,f"reasoning_tokens={rt} "+d["choices"][0]["message"]["content"][:80].replace("\n"," "),round(time.perf_counter()-t,1)
async def main():
    async with httpx.AsyncClient(timeout=300) as c:
        res=await asyncio.gather(
            claude(c,"claude-opus-5-5",False), claude(c,"claude-opus-5-5",True),
            claude(c,"claude-fable-5-1",False), claude(c,"claude-fable-5-1",True),
            claude(c,"claude-sonnet-5-5",True),
            gpt(c,"gpt-6-astra",None), gpt(c,"gpt-6-astra","high"), gpt(c,"gpt-6-astra","xhigh"),
            gpt(c,"gpt-6.1-sol",None), gpt(c,"gpt-6.1-sol","high"),
            gpt(c,"gpt-5.6-luna-max",None),
            gpt(c,"grok-4.7",None), gpt(c,"deep-seek-v4-pro",None), gpt(c,"kimi-k3",None), gpt(c,"nemotron-3-ultra",None),
        )
    for m,mode,code,txt,s in res: print(f"{m:20} {mode:6} {code} {s:>5}s  {txt}")
asyncio.run(main())
