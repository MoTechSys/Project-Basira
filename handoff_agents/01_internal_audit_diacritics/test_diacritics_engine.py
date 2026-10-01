"""Reproducible mechanical tests, NOT a scholarly correctness benchmark.
python test_diacritics_engine.py ../prototype_audit_source/corpus/data/tanzil-uthmani.txt
Preserves the user's two strings verbatim. Full corpus is read locally, not redistributed.
"""
import hashlib
import html
import json
from pathlib import Path
import statistics
import sys
import time
import unicodedata as ud
from collections import Counter
from diacritics_engine import compare, BASIC

USER = '﴿ ۞ قُلْ يَا عِبَادِيَ الَّذِينَ أَسرَفُوا عَلَىٰ أَنفُسِهِمْ لَا تَقْنَطُوا مِن رَّحْمَةِ اللَّهِ  إِنَّ اللهَ يَغْفِرُ الذُّنوبَ جَمِيعًا ۚ إِنَّهُ هُوَ الْغَفُورُ الرَّحِيمُ﴾'
GIVEN = '﴿ ۞ قُلْ يَا عِبَادِيَ الَّذِينَ أَسْرَفُوا عَلَىٰ أَنفُسِهِمْ لَا تَقْنَطُوا مِن رَّحْمَةِ اللَّهِ ۚ إِنَّ اللَّهَ يَغْفِرُ الذُّنُوبَ جَمِيعًا ۚ إِنَّهُ هُوَ الْغَفُورُ الرَّحِيمُ﴾'
E = Path(__file__).resolve().parent/'evidence'

def run():
    corpus=Path(sys.argv[1]);data=corpus.read_bytes()
    expected_sha='bf4f57b968d03f4131c070b1e285da9be0e0a108a21c910e872801ca273312c8'
    assert hashlib.sha256(data).hexdigest()==expected_sha,'wrong pinned source'
    records=[]
    for line in data.decode().splitlines():
        if line and line[0].isdigit():
            s,a,t=line.split('|',2);records.append((int(s),int(a),t))
    assert len(records)==6236
    suite=[]
    def check(name,q,s,expected):
        r=compare(q,s);ok=r['comparison_status']==expected
        # Every supplied range is a valid slice into the original, not a normalized string.
        for e in r['events']:
            for text,key in [(q,'user'),(s,'source')]:
                a,b=e[key+'_range'];assert 0<=a<=b<=len(text)
                assert e[key+'_utf16']==[len(text[:a].encode('utf-16-le'))//2,len(text[:b].encode('utf-16-le'))//2]
        suite.append({'id':name,'pass':ok,'expected':expected,'actual':r['comparison_status'],'input':q,'reference':s})
        return r
    for c in sorted(BASIC):
        check('missing_'+hex(ord(c)),'ب','ب'+c,'vocalization_incomplete')
        check('duplicate_'+hex(ord(c)),'ب'+c+c,'ب'+c,'needs_review')
    for c in 'ًٌٍَُِْ':
        check('replace_'+hex(ord(c)),'ب'+('ُ' if c!='ُ' else 'َ'),'ب'+c,'needs_review')
    for n,s in enumerate(['رَْٰٔ','ـِّۧ','ـِۧ','ۦَ']):
        check(f'complex_identity_{n}',s,s,'exact')
        check(f'complex_changed_{n}',s[:-1],s,'needs_review')
    check('hamza_carrier','ـَٔ','ـَٔ','exact')
    check('hamza_carrier_deleted','ـَ','ـَٔ','needs_review')
    fixed=[
      ('final_vowel','اللَّهُ','اللَّهَ','needs_review'),
      ('internal_vowel','يُغْفِرُ','يَغْفِرُ','needs_review'),
      ('missing_nun','الذُّنوبَ','الذُّنُوبَ','vocalization_incomplete'),
      ('shadda_order','بَّ','بَّ','matching_with_notices'),
      ('decomposed_hamza','ا\u0654','أ','matching_with_notices'),
      ('hamza_removed','ا','أ','needs_review'),
      ('superscript_alef_missing','على','علىٰ','needs_review'),
      ('zero_is_not_sukun','اْ','ا۟','needs_review'),
      ('pause_missing','اللَّهِ إِنَّ','اللَّهِ ۚ إِنَّ','matching_with_notices'),
      ('stop_relocated','ۚ قُلْ هُوَ','قُلْ ۚ هُوَ','matching_with_notices'),
      ('latin_insert','قُلْ HELLO هُوَ','قُلْ هُوَ','needs_review'),
      ('number_insert','قُلْ 123 هُوَ','قُلْ هُوَ','needs_review'),
      ('bidi_control','قُلْ\u202e هُوَ','قُلْ هُوَ','needs_review'),
      ('joiner','قُ\u200dلْ','قُلْ','needs_review'),
      ('orphan','ُ قُلْ','قُلْ','needs_review'),
      ('empty','','','needs_review'),
      ('latin_reference','HELLO','HELLO','needs_review'),
      ('missing_letter','قُلْ هُ','قُلْ هُوَ','needs_review'),
      ('word_boundary','قُلْهُوَ','قُلْ هُوَ','needs_review'),
      ('astral_offsets','\U0001F642 اللَّهُ','اللَّهَ','needs_review'),
      ('foreign_combining','ب\u0301','ب','needs_review'),
      ('presentation_ligature','ﻻ','لا','needs_review'),
    ]
    for x in fixed:check(*x)
    sample=check('user_literal_example',USER,GIVEN,'vocalization_incomplete')
    tally=Counter(e['kind'] for e in sample['events'])
    assert tally['missing_vowel']==3 and tally['missing_shadda']==1 and tally['pause_mark_missing']==1,tally
    check('fully_stripped',''.join(c for c in GIVEN if c not in BASIC),GIVEN,'vocalization_incomplete')
    case16='إِنَّمَا يَخْشَى اللَّهُ مِنْ عِبَادِهِ الْعُلَمَاءَ'
    check('case16_same_orthography',case16,'إِنَّمَا يَخْشَى اللَّهَ مِنْ عِبَادِهِ الْعُلَمَاءُ','needs_review')
    # The preceding reference is a user-style comparison fixture, NOT a new canonical corpus.
    counts=Counter();failures=[];unsupported=[];t0=time.perf_counter()
    def record(name,r,want,ref):
        counts[name+'_total']+=1
        if r['comparison_status'] in want:counts[name+'_passed']+=1
        elif len(failures)<30:failures.append({'test':name,'ref':ref,'status':r['comparison_status'],'events':r['events'][:3]})
    for surah,ayah,text in records:
        ref=f'{surah}:{ayah}'
        r=compare(text,text)
        record('identity',r,{'exact'},ref)
        if r['comparison_status']!='exact':unsupported.append(ref)
        nfd=compare(ud.normalize('NFD',text),text)
        record('canonical_nfd',nfd,{'exact','matching_with_notices'},ref)
        positions=[i for i,c in enumerate(text) if c in BASIC]
        if not positions:continue
        # Choose LAST basic mark to catch the original final-character blind spot.
        i=positions[-1];mark=text[i]
        delete=text[:i]+text[i+1:]
        r=compare(delete,text)
        record('last_mark_deletion',r,{'vocalization_incomplete'},ref)
        altered='ُ' if mark!='ُ' else 'َ'
        r=compare(text[:i]+altered+text[i+1:],text)
        record('last_mark_substitution',r,{'needs_review'},ref)
        r=compare(text[:i]+mark+text[i:],text)
        record('last_mark_duplication',r,{'needs_review'},ref)
    elapsed=time.perf_counter()-t0
    timings=[]
    for _ in range(200):
        start=time.perf_counter();compare(USER,GIVEN);timings.append((time.perf_counter()-start)*1000)
    tanzil39=next(t for s,a,t in records if(s,a)==(39,53))
    result={'date':'2026-10-01','source_sha256':hashlib.sha256(data).hexdigest(),
       'source_url':'https://tanzil.net/pub/download/index.php?quranType=uthmani&outType=txt-2&agree=true',
       'source_license_url':'https://tanzil.net/docs/text_license','corpus_records':len(records),
       'targeted_cases':suite,'targeted_passed':sum(x['pass'] for x in suite),
       'corpus_checks':dict(counts),'corpus_failures':failures,'unsupported_identity_refs':unsupported,
       'corpus_seconds':elapsed,'same_rasm_pair_latency_ms':{'n':200,'p50':statistics.median(timings),'p95':sorted(timings)[189],'max':max(timings)},
       'user_literal':USER,'supplied_reference_literal':GIVEN,'sample_result':sample,
       'user_vs_pinned_uthmani':compare(USER,tanzil39),
       'notes':['Mechanical same-source mutations; not independent religious review.',
                'Supplied second string is a comparison fixture, not independently authenticated full-vocalized Imlaei source.',
                'No cross-rasm equivalence, reading authentication, retrieval, attribution, or OCR is provided by this comparator.']}
    (E/'diacritics_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    # Standalone local diagnostic report. All user/source strings escaped; no auto-correct or executable input.
    names={'missing_vowel':'حركة/سكون ناقص','missing_shadda':'شدة ناقصة','pause_mark_missing':'علامة وقف ناقصة'}
    rows=[]
    for event in sample['events']:
        a,b=event['user_range'];c,d=event['source_range']
        rows.append('<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in [names.get(event['kind'],event['kind']),USER[max(0,a-8):min(len(USER),b+8)],GIVEN[max(0,c-8):min(len(GIVEN),d+8)],'◌'+event['expected'],' / '.join(event['expected_codepoints']),str([a,b])])+'</tr>')
    report='<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>فروق مثال المستخدم</title><style>body{max-width:1100px;margin:40px auto;padding:20px;font:20px sans-serif;line-height:1.8}p.quote{font:28px "Noto Naskh Arabic",serif;white-space:pre-wrap;border:1px solid #aaa;padding:20px}table{border-collapse:collapse;width:100%}td,th{padding:12px;border:1px solid #bbb}</style><h1>تقرير داخلي: الفروق في المثال الحرفي</h1><p>مقارنة بين النصين اللذين أرسلهما المستخدم؛ ليست اعتمادًا للنص الثاني كمصدر قرآني. النصان محفوظان بلا تعديل. علامة الدائرة في الجدول لعرض الحركة وحدها فقط.</p><h2>النص المدخل</h2><p class="quote">'+html.escape(USER)+'</p><h2>النص المقارن المرسل</h2><p class="quote">'+html.escape(GIVEN)+'</p><h2>الفروق</h2><table><tr><th>النوع</th><th>حول موضع المستخدم</th><th>حول موضع المقارنة</th><th>الناقص</th><th>Unicode</th><th>offset</th></tr>'+''.join(rows)+'</table><p>النتيجة: نقص ضبط وعلامة وقف، لا ادعاء تغيير معنى أو تحريف. لا فحص قراءات أو تفسير آلي.</p></html>'
    (E/'diacritics_example.html').write_text(report)
    print(json.dumps({k:result[k] for k in ['targeted_passed','corpus_checks','corpus_seconds','same_rasm_pair_latency_ms']},indent=2))
    print('Targeted total',len(suite),'unsupported identities',len(unsupported),'failures',len(failures))
    if failures or not all(x['pass'] for x in suite):raise SystemExit(1)

if __name__=='__main__':run()
