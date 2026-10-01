import json,csv,numpy as np,sys,collections
from sklearn.metrics import f1_score
C={'Ayah':1,'matn':2,'isnad':3,'claimed_source':4}
D='.scratch/islamiceval2026/dev_set/'
resp={json.loads(l)['id']:json.loads(l)['generated_answer'] for l in open(D+'dev.jsonl')}
def lab(path):
    L={k:np.zeros(len(v),int) for k,v in resp.items()}
    for r in csv.DictReader(open(path,newline=''),delimiter='\t'):
        t=r['Segment_Type'].strip()
        if t in C: L[r['Response_ID']][int(r['Span_Start']):int(r['Span_End'])]=C[t]
    return L
G=lab(D+'dev_task_1.tsv'); P=lab(sys.argv[1] if len(sys.argv)>1 else 'eval/islamiceval/predictions_2026_task1_dev.tsv')
g=np.concatenate([G[k] for k in resp]); p=np.concatenate([P[k] for k in resp])
f=f1_score(g,p,labels=[1,2,3,4],average=None); print({k:round(v,3) for k,v in zip(C,f)}, 'macro', round(f.mean(),4))
cm=collections.Counter(zip(g.tolist(),p.tolist()))
print('rows gold (neither,Ayah,matn,isnad,cs) x pred'); [print(a,[cm[(a,b)] for b in range(5)]) for a in range(5)]
