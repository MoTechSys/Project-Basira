def L(h):
    h=h.lstrip('#'); c=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    c=[x/12.92 if x<=.03928 else ((x+.055)/1.055)**2.4 for x in c]; return .2126*c[0]+.7152*c[1]+.0722*c[2]
def cr(a,b): x,y=sorted([L(a),L(b)],reverse=True); return (x+.05)/(y+.05)
T=dict(paper="#F6F2E9",sheet="#FFFDF8",ink="#12183F",body="#333A5F",muted="#5D6283",rule="#E5DECF",rule2="#D6CDB9",
 violet="#5B48E8",violet_ink="#4A37E7",
 found="#0B6B52",found_bg="#E1F0E6",partial="#2E42B5",partial_bg="#E6E9F7",review="#8A4300",review_bg="#FAE9C8",nf="#4B5070",nf_bg="#EAE6DC")
TEXT=[("ink","paper"),("ink","sheet"),("body","sheet"),("muted","sheet"),("muted","paper"),("sheet","ink"),("violet_ink","sheet"),("violet_ink","paper"),
 ("found","found_bg"),("partial","partial_bg"),("review","review_bg"),("nf","nf_bg"),("found","sheet"),("partial","sheet"),("review","sheet"),("nf","sheet"),
 ("ink","found_bg"),("ink","review_bg"),("ink","partial_bg"),("ink","nf_bg"),("muted","nf_bg")]
GRAPHIC=[("violet","paper"),("violet","sheet"),("rule2","sheet"),("found","paper"),("review","paper"),("partial","paper"),("nf","paper"),("ink","paper")]
if __name__=="__main__":
    bad=0
    for a,b in TEXT:
        r=cr(T[a],T[b]); ok=r>=4.5; bad+=not ok; print(f"text    {'PASS' if ok else 'FAIL'} {r:5.2f}  {a} on {b}")
    for a,b in GRAPHIC:
        r=cr(T[a],T[b]); ok=r>=3 or a.startswith('rule'); print(f"graphic {'PASS' if r>=3 else 'decor'} {r:5.2f}  {a} on {b}")
    print("text failures:",bad)
