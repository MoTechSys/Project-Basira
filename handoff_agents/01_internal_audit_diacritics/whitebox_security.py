#!/usr/bin/env python3
"""Local synthetic audit only; run with prototype backend venv, passing checkout path.
No source changes. Unit witnesses distinguish validator limitations from HTTP exploitability.
"""
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCE=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(SOURCE/'backend'))
from app.config import Settings, Thresholds
from app.state import decide, QuoteFacts, Evidence
from app.schemas import CheckResponse
from app.verify import validate_response
from app.snapshot import load_or_build
from app.main import RateLimiter
from app.match.harakat import word_conflicts

store,_=load_or_build(SOURCE/'corpus/index',write=False)
rows=json.loads((ROOT/'evidence/cases_actual.json').read_text())
response=CheckResponse.model_validate(rows[16]['response'])
response.quotes[0].quoted_text='هذا نص مختلف تماما'
response.quotes[0].span.end=999999
response.quotes[0].message_key='nonexistent_key'
validate_response(response,store,SOURCE/'messages',hadeethenc_link=True)
r={'validator_tamper':{'status':response.quotes[0].status,'rejections':response.validator_rejections,'span_end':response.quotes[0].span.end,'message_key':response.quotes[0].message_key},
   'short_marked_state':decide(QuoteFacts(3,'ar','hadith_matn',True),[Evidence('hadeethenc',0,.9,False)],Thresholds()).status,
   'short_unmarked_state':decide(QuoteFacts(3,'ar','hadith_matn',False),[Evidence('hadeethenc',0,.9,False)],Thresholds()).status,
   'final_vowel_conflicts':len(word_conflicts('اللَّهُ','اللَّهَ'))}
lim=RateLimiter(30)
for i in range(10002):lim.allow(str(i),now=1.)
r['active_rate_keys']=len(lim._hits)

def post(text,ip):
    req=urllib.request.Request('http://127.0.0.1:8000/v1/check',json.dumps({'text':text}).encode(),{'Content-Type':'application/json','X-Forwarded-For':ip})
    try:
        with urllib.request.urlopen(req,timeout=20) as resp:return resp.status
    except urllib.error.HTTPError as exc:return exc.code
r['xff_rate_same_ip']=[post('مرحبا بالعالم','192.0.2.123') for _ in range(31)]
r['xff_rate_changed_ip']=post('مرحبا بالعالم','192.0.2.124')

def image(data,mime,name):
    boundary='BasiraAuditBoundary'
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n').encode()+data+f'\r\n--{boundary}--\r\n'.encode()
    req=urllib.request.Request('http://127.0.0.1:8000/v1/check/image',body,{'Content-Type':f'multipart/form-data; boundary={boundary}','X-Eval-Key':'local-audit-only'})
    try:
        with urllib.request.urlopen(req,timeout=30) as resp:return {'status':resp.status,'body':json.load(resp)}
    except urllib.error.HTTPError as exc:return {'status':exc.code,'body':json.loads(exc.read())}
r['fake_png']=image(b'not a real image','image/png','fake.png')
if (ROOT/'evidence/case28.png').exists():
    r['case28_image']=image((ROOT/'evidence/case28.png').read_bytes(),'image/png','case28.png')
r['bad_mime']=image(b'test','text/plain','test.txt')
r['oversized']=image(b'a'*(6*1024*1024+1),'image/png','big.png')
(ROOT/'evidence/whitebox_security.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
print(json.dumps(r,ensure_ascii=False,indent=2))
