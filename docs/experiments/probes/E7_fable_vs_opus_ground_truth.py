"""Does Fable 5.1 'never err'? Test on tasks with a deterministic ground truth we can check."""
import asyncio, os, json, re, httpx, hashlib
A=os.environ["ANTHROPIC_BASE_URL"]+"/v1/messages"; H={"x-api-key":os.environ["ANTHROPIC_API_KEY"],"anthropic-version":"2023-06-01"}

async def ask(c, model, prompt, think=True):
    body={"model":model,"max_tokens":6000,"messages":[{"role":"user","content":prompt}]}
    if think: body["thinking"]={"type":"enabled","budget_tokens":4000}
    r=await c.post(A,headers=H,json=body); d=r.json()
    return " ".join(b.get("text","") for b in d.get("content",[]) if b.get("type")=="text")

# Ground truths computed locally (never by a model)
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
TESTS=[
 ("arith",  "Compute exactly: 48213 * 7391. Reply with ONLY the integer.", str(48213*7391)),
 ("count",  "How many letters 'r' are in the word 'strawberry'? Reply with ONLY the integer.", "3"),
 ("regex",  "Write ONLY a Python regex (no code fences, no explanation) that matches Arabic-Indic digits ٠-٩ (U+0660–U+0669) one or more times.", None),
 ("quran",  "What is the 7th verse of Surah Al-Fatiha in Arabic? Reply ONLY with the verse text, no diacritics.", "صراط الذين انعمت عليهم غير المغضوب عليهم ولا الضالين"),
 ("fact",   "Who is the author of the hadith collection 'Sunan al-Darimi'? Reply with ONLY the author's full name and death year (Hijri).", "255"),
 ("python", "Return ONLY valid Python (no fences) defining function lev(a:str,b:str)->int computing Levenshtein distance.", None),
]

def check(name, out, truth):
    o=out.strip()
    if name=="arith": return o==truth, o
    if name=="count": return o==truth, o
    if name=="regex":
        try: rx=re.compile(o); ok=bool(rx.fullmatch("٠١٢٣٤٥٦٧٨٩")) and not rx.search("abc"); return ok, o
        except Exception as e: return False, f"invalid regex: {e}"
    if name=="quran":
        import unicodedata
        norm=lambda s: re.sub(r"[\u064B-\u0652\u0670]","",s).replace("أ","ا").replace("إ","ا").replace("آ","ا").replace("ٱ","ا").replace("ى","ي").strip()
        return norm(o)==norm(truth), o
    if name=="fact": return "255" in o and ("دارمي" in o or "Darimi" in o or "Dārimī" in o), o
    if name=="python":
        ns={}
        try:
            exec(o,ns); f=ns["lev"]
            ok = f("kitten","sitting")==3 and f("","abc")==3 and f("same","same")==0 and f("إن","إنّ")==1
            return ok, o[:80].replace("\n"," ")
        except Exception as e: return False, f"exec error: {e}"

async def main():
    async with httpx.AsyncClient(timeout=300) as c:
        for model in ["claude-fable-5-1","claude-opus-5-5"]:
            print(f"\n===== {model} =====")
            outs=await asyncio.gather(*[ask(c,model,p) for _,p,_ in TESTS])
            score=0
            for (name,_,truth),out in zip(TESTS,outs):
                ok,shown=check(name,out,truth); score+=ok
                print(f"  {'✓' if ok else '✗'} {name:7} → {shown[:90]}")
            print(f"  SCORE {score}/{len(TESTS)}")
asyncio.run(main())
