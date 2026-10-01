"""Experimental deterministic, same-orthography comparator, NOT a religious validator.
Requires regex==2026.7.19. Source selection/authentication/reading are caller responsibilities.
Never edits either input, never emits repaired religious text. No cross-rasm guessing.
Offsets: Unicode code points, half-open; UTF-16 equivalents provided for browser consumers.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import hashlib
import unicodedata as ud
import regex

BASIC = frozenset(chr(i) for i in range(0x64B, 0x653))
VOWELS = BASIC - {'\u0651'}
PAUSE = frozenset(chr(i) for i in range(0x6D6, 0x6DC))
ORTHOGRAPHIC = frozenset('\u0653\u0670\u06dc\u06df\u06e0\u06e1\u06e2\u06e3\u06e4\u06e5\u06e6\u06e7\u06e8\u06ea\u06eb\u06ec\u06ed')
LAYOUT = frozenset('﴿﴾۞۩ـ«»“”"()[]{}،؛:,.!?؟')
LIMIT = 5000
REMOVABLE = BASIC | ORTHOGRAPHIC | PAUSE | LAYOUT
KNOWN_MARKS = BASIC | ORTHOGRAPHIC | PAUSE | {'\u0654', '\u0655'}
DECORATION = PAUSE | LAYOUT

@dataclass
class Unit:
    key: str
    start: int
    end: int
    marks: Counter = field(default_factory=Counter)
    orthographic: tuple[str, ...] = ()


def _utf16_prefix(text):
    p=[0]
    for c in text:p.append(p[-1]+(2 if ord(c)>0xFFFF else 1))
    return p


def _parse(text):
    units=[]; decoration=[]; invalid=[]; anchor=0
    for m in regex.finditer(r'\X',text):
        raw=m.group(); nfc=ud.normalize('NFC',raw)
        # Work only on a comparison projection. Raw source is never rewritten.
        core=''.join(c for c in nfc if c not in REMOVABLE)
        # In this Uthmani encoding tatweel can CARRY HAMZA, not merely decorate a word.
        # Preserve it in the signature; never discard the hamza or guess another spelling.
        hamza_carrier='ـ' in nfc and any(c in nfc for c in '\u0654\u0655')
        if hamza_carrier:core='ـ'+core
        core=' '.join(core.split()) if core.strip() else (' ' if any(c.isspace() for c in core) else '')
        for c in raw:
            if c in DECORATION:decoration.append((anchor,c,m.start(),m.end()))
            if ud.category(c) in {'Cf','Cs','Co','Cn'} or (ud.category(c).startswith('M') and c not in KNOWN_MARKS):
                invalid.append((m.start(),m.end(),'unsupported_or_control'))
        # A few Uthmani graphemes encode more than one phonographic component.
        # Do not assign their marks to an invented base letter. Preserve the WHOLE
        # canonical cluster as an opaque key: equality only; any change needs review.
        complex_carrier=('ـ' in nfc and '\u06e7' in nfc) or nfc[0] in '\u06e5\u06e6'
        complex_hamza='\u0670' in nfc and '\u0654' in nfc and sum(c in VOWELS for c in nfc)>1
        if complex_carrier or complex_hamza:
            if all(c in KNOWN_MARKS or ('ARABIC' in ud.name(c,'') and ud.category(c).startswith('L')) for c in nfc):
                units.append(Unit('opaque:'+nfc,m.start(),m.end()))
                anchor+=1
                continue
        marks=Counter(c for c in nfc if c in BASIC)
        orth=tuple(c for c in nfc if c in ORTHOGRAPHIC)
        if not core:
            if marks:invalid.append((m.start(),m.end(),'orphan_mark'))
            for c in orth:decoration.append((anchor,c,m.start(),m.end()))
            continue
        if core==' ':
            if marks:invalid.append((m.start(),m.end(),'orphan_mark'))
            for c in orth:decoration.append((anchor,c,m.start(),m.end()))
            if units and units[-1].key!=' ':units.append(Unit(' ',m.start(),m.end()))
            continue
        if any(not (('ARABIC' in ud.name(c,'') and ud.category(c).startswith('L')) or (hamza_carrier and c in '\u0654\u0655')) for c in core):
            invalid.append((m.start(),m.end(),'foreign_or_unsupported_content'))
        if any(n>1 for n in marks.values()) or sum(marks[v] for v in VOWELS)>1:
            invalid.append((m.start(),m.end(),'duplicate_or_conflicting_marks'))
        units.append(Unit(core,m.start(),m.end(),marks,orth))
        anchor+=1
    if units and units[-1].key==' ':units.pop()
    return units,decoration,invalid


def compare(user: str, source: str) -> dict:
    if not isinstance(user,str) or not isinstance(source,str):raise TypeError('text inputs required')
    if len(user)>LIMIT or len(source)>LIMIT:raise ValueError('comparison length limit exceeded')
    qu,qd,qi=_parse(user); su,sd,si=_parse(source)
    qp=_utf16_prefix(user);sp=_utf16_prefix(source)
    events=[]
    def emit(kind,qs,ss,observed='',expected='',severity='review'):
        events.append({'kind':kind,'severity':severity,'user_range':list(qs),'source_range':list(ss),
                       'user_utf16':[qp[qs[0]],qp[qs[1]]], 'source_utf16':[sp[ss[0]],sp[ss[1]]],
                       'observed':observed,'expected':expected,
                       'observed_codepoints':[f'U+{ord(c):04X}' for c in observed],
                       'expected_codepoints':[f'U+{ord(c):04X}' for c in expected]})
    for a,b,kind in qi:emit(kind,(a,b),(0,0),user[a:b])
    for a,b,kind in si:emit('source_'+kind,(0,0),(a,b),expected=source[a:b])
    keys_equal=[u.key for u in qu]==[u.key for u in su] and any(u.key!=' ' for u in qu)
    if keys_equal:
        blocks=[('equal',0,len(qu),0,len(su))]
    else:
        blocks=SequenceMatcher(None,[u.key for u in qu],[u.key for u in su],autojunk=False).get_opcodes()
        # Diagnostic alignment is not evidence of equivalence, even where fragments align.
        def span(units,a,b,text):
            return (units[a].start,units[b-1].end) if a<b else ((units[a].start,)*2 if a<len(units) else (len(text),)*2)
        for op,a,b,c,d in blocks:
            if op!='equal':
                qr=span(qu,a,b,user);sr=span(su,c,d,source)
                emit('letter_or_word_boundary_difference',qr,sr,user[qr[0]:qr[1]],source[sr[0]:sr[1]])
    for op,a,b,c,d in blocks:
        if op!='equal':continue
        for q,s in zip(qu[a:b],su[c:d],strict=True):
            qr=(q.start,q.end);sr=(s.start,s.end)
            qv=Counter({k:v for k,v in q.marks.items() if k in VOWELS})
            sv=Counter({k:v for k,v in s.marks.items() if k in VOWELS})
            if qv!=sv:
                kind='vowel_conflict' if qv and sv else ('missing_vowel' if sv else 'additional_vowel_not_in_reference')
                emit(kind,qr,sr,''.join(qv.elements()),''.join(sv.elements()),'notice' if not qv else 'review')
            qsh=q.marks['\u0651'];ssh=s.marks['\u0651']
            if qsh!=ssh:
                emit('missing_shadda' if ssh>qsh else 'additional_shadda',qr,sr,'\u0651'*qsh,'\u0651'*ssh,'notice' if ssh>qsh else 'review')
            if q.orthographic!=s.orthographic:
                emit('orthographic_mark_difference',qr,sr,''.join(q.orthographic),''.join(s.orthographic))
    # Punctuation and pause annotations are a separate channel, never collapsed into vowel marks.
    if keys_equal:
        qc=Counter((a,c) for a,c,_,_ in qd);sc=Counter((a,c) for a,c,_,_ in sd)
        for side,items,diff in [('user',qd,qc-sc),('source',sd,sc-qc)]:
            remaining=diff.copy()
            for anchor,ch,a,b in items:
                if not remaining[(anchor,ch)]:continue
                remaining[(anchor,ch)]-=1
                is_orth=ch in ORTHOGRAPHIC
                kind=('orthographic_symbol_' if is_orth else 'pause_mark_' if ch in PAUSE else 'layout_')+('added' if side=='user' else 'missing')
                # Anchor the missing annotation to the matching preceding user grapheme.
                other=[u for u in (su if side=='user' else qu) if u.key!=' ']
                at=(other[min(anchor-1,len(other)-1)].end if anchor and other else 0)
                emit(kind,(a,b) if side=='user' else (at,at),(at,at) if side=='user' else (a,b),ch if side=='user' else '',ch if side=='source' else '', 'review' if is_orth else 'notice')
    if user!=source and not events:
        emit('canonical_or_spacing_difference',(0,len(user)),(0,len(source)),severity='notice')
    if not any(u.key!=' ' for u in su):emit('empty_reference',(0,0),(0,0))
    review=any(e['severity']=='review' for e in events)
    missing=any(e['kind'] in {'missing_vowel','missing_shadda'} for e in events)
    state='needs_review' if review or not keys_equal else 'vocalization_incomplete' if missing else 'matching_with_notices' if events else 'exact'
    return {'comparison_status':state,'same_letter_and_word_sequence':keys_equal,
            'fully_identical_raw':user==source,'events':events,
            'user_sha256':hashlib.sha256(user.encode()).hexdigest(),
            'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'unicode_database':ud.unidata_version,'grapheme_library':regex.__version__,
            'source_authentication':'not_performed_by_comparator',
            'scope':'same orthography; complex clusters require exact canonical equality; no meaning or authenticity judgments'}
