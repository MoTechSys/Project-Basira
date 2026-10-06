"""Draw rich_message blocks (Bot API shape) as a Telegram-like dark bubble, for review: preview_blocks.py in.json out.html"""
import json, sys, html
def rt(t):
    if t is None: return ""
    if isinstance(t, str): return html.escape(t).replace("\n","<br>")
    if isinstance(t, list): return "".join(rt(x) for x in t)
    ty=t.get("type"); inner=rt(t.get("text"))
    return {"bold":f"<b>{inner}</b>","italic":f"<i>{inner}</i>","marked":f"<mark>{inner}</mark>","code":f"<code>{inner}</code>",
            "url":f"<a>{inner}</a>","superscript":f"<sup>{inner}</sup>"}.get(ty, inner)
def blk(b):
    t=b["type"]
    if t=="heading": return f"<h{b['size']}>{rt(b['text'])}</h{b['size']}>"
    if t=="paragraph": return f"<p>{rt(b['text'])}</p>"
    if t=="divider": return "<hr>"
    if t=="footer": return f"<footer>{rt(b['text'])}</footer>"
    if t=="blockquote": return f"<blockquote>{''.join(blk(x) for x in b['blocks'])}<cite>{rt(b.get('credit'))}</cite></blockquote>"
    if t=="pullquote": return f"<aside><div class=q>{rt(b['text'])}</div><cite>{rt(b.get('credit'))}</cite></aside>"
    if t=="table":
        rows="".join("<tr>"+"".join((f"<th>{rt(c['text'])}</th>" if c.get('is_header') else f"<td>{rt(c['text'])}</td>") for c in r)+"</tr>" for r in b["cells"])
        cap=f"<caption>{rt(b.get('caption'))}</caption>" if b.get('caption') else ""
        return f"<table>{cap}{rows}</table>"
    if t=="details": return f"<details {'open' if b.get('is_open') else ''}><summary>{rt(b['summary'])}</summary>{''.join(blk(x) for x in b['blocks'])}</details>"
    if t=="list": return "<ul>"+"".join("<li>"+"".join(blk(x) for x in i["blocks"])+"</li>" for i in b["items"])+"</ul>"
    if t=="buttons": return "<div class=btns>"+"".join(f"<span class='btn {x.get('style','')}'>{html.escape(x['text'])}</span>" for x in b["buttons"])+"</div>"
    return f"<p>[{t}]</p>"
CSS="""body{margin:0;background:#0e1621;font-family:'Noto Naskh Arabic','Amiri',sans-serif;direction:rtl;padding:18px}
.bubble{max-width:430px;background:#182533;color:#e9eef3;border-radius:16px;padding:14px 16px;font-size:15px;line-height:1.65}
h1{font-size:23px;margin:4px 0 8px}h2{font-size:20px;margin:4px 0 8px}h3{font-size:17px;margin:10px 0 6px;color:#fff}
p{margin:6px 0}hr{border:0;border-top:1px solid #2b3a4a;margin:12px 0}mark{background:#d9b66e;color:#12183f;border-radius:3px;padding:0 2px}
blockquote{border-right:3px solid #6ab3f3;margin:8px 0;padding:4px 10px;background:#1e2c3a;border-radius:6px}
aside{margin:10px 0;padding:10px 14px;text-align:center;font-size:19px;font-family:'Amiri';border-top:1px solid #2b3a4a;border-bottom:1px solid #2b3a4a}
cite{display:block;font-size:12px;color:#8ea2b5;font-style:normal;margin-top:4px}aside cite{font-family:'Noto Naskh Arabic'}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:8px 0}th,td{border:1px solid #2b3a4a;padding:4px 8px;color:#e9eef3}th{color:#8ea2b5;font-weight:600;white-space:nowrap}
details{background:#1e2c3a;border-radius:8px;padding:6px 10px;margin:6px 0}summary{color:#6ab3f3;cursor:pointer}ul{margin:4px 0;padding-right:18px}
footer{font-size:12px;color:#8ea2b5}code{background:#0e1621;padding:0 4px;border-radius:4px;font-size:12px}a{color:#6ab3f3}
.btns{display:flex;gap:6px;margin:6px 0}.btn{flex:1;text-align:center;background:#2b5278;border-radius:8px;padding:7px 4px;font-size:13px}
.btn.primary{background:#3a7bd5}.btn.success{background:#2f9e5b}sup{font-size:11px;color:#8ea2b5}"""
docs=json.load(open(sys.argv[1]))
out="<html><head><meta charset=utf-8><style>"+CSS+"</style></head><body>"+"".join("<div class=bubble style='margin-bottom:16px'>"+"".join(blk(b) for b in d["blocks"])+"</div>" for d in docs)+"</body></html>"
open(sys.argv[2],"w").write(out)
