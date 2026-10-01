import json, sys, time, collections
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'backend')); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO/'eval'/'islamiceval'))
from run_1b import basira_status, map_label
from app.config import Settings
from app.pipeline import CorpusMeta, Pipeline
from app.providers import MockLLM
from app.retrieve.index import Retriever
from app.store import load_store
s = Settings(index_dir=REPO/'corpus/index'); store = load_store(s.index_dir)
man = json.loads(s.manifest_path.read_text())
pipe = Pipeline(store, Retriever(store), MockLLM(), s, CorpusMeta.from_manifest(man, store.meta))
rows = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv)>1 else '.scratch/islamiceval2026/dev_set/dev.jsonl')]
res = collections.defaultdict(collections.Counter); stat = collections.Counter(); dangerous=[]; t0=time.time()
for r in rows:
    ans = r['generated_answer']
    for a in r.get('annotations') or []:
        for sg in a.get('segments', []):
            if sg['type'] not in ('Ayah','matn') or sg['label'] not in ('correct','incorrect'): continue
            txt = ans[sg['span_start']:sg['span_end']]
            kind = 'quran' if sg['type']=='Ayah' else 'hadith_matn'
            st, reason, scope, top, notes = basira_status(pipe, txt, kind)
            pred = 'correct' if map_label(st, scope, kind)=='Correct' else 'incorrect'
            res[sg['type']][(sg['label'], pred)] += 1
            stat[(sg['type'], sg['label'], st)] += 1
            if sg['label']=='incorrect' and pred=='correct': dangerous.append((r['id'], sg['type'], txt[:100], top, a.get('correction')))
print('secs', round(time.time()-t0,1))
accs=[]
for t,c in res.items():
    n=sum(c.values()); k=c[('correct','correct')]+c[('incorrect','incorrect')]; accs.append(k/n)
    print(t, 'acc', round(100*k/n,2), 'n', n, dict(c))
print('macro(Ayah,matn)', round(100*sum(accs)/len(accs),2))
for k,v in sorted(stat.items()): print(k,v)
print('DANGEROUS', len(dangerous))
for d in dangerous[:15]: print(json.dumps(d, ensure_ascii=False)[:400])
