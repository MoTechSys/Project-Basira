"""Build OG (1200x630) + Twitter square (600x600) with correct Arabic shaping & bidi.
Text is rendered via PIL ImageFont with libraqm when available; fallback = uharfbuzz + bidi."""
import os, io, cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from bidi.algorithm import get_display

HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
FONT='/tmp/fonts/ReadexPro.ttf'
BG=os.path.join(ROOT,'..','handoff','template','assets','ppt','media','image3.png')
RAQM = features.check('raqm')
print("raqm:", RAQM)

def font(size, wght):
    f=ImageFont.truetype(FONT, size)
    try: f.set_variation_by_axes([wght, 0])
    except Exception: pass
    return f

def draw_text(d, xy, text, f, fill, anchor='ra'):
    """Right-anchored Arabic/mixed text with correct bidi."""
    if RAQM:
        d.text(xy, text, font=f, fill=fill, anchor=anchor, direction='rtl', features=['calt','liga','mark','mkmk'])
    else:
        d.text(xy, get_display(text), font=f, fill=fill, anchor=anchor)

def svg_png(path, width):
    return Image.open(io.BytesIO(cairosvg.svg2png(url=path, output_width=width))).convert('RGBA')

def og():
    W,H=1200,630
    bg=Image.open(BG).convert('RGB')
    s=max(W/bg.width, H/bg.height); bg=bg.resize((round(bg.width*s),round(bg.height*s)), Image.LANCZOS)
    x=(bg.width-W)//2; y=(bg.height-H)//2; im=bg.crop((x,y,x+W,y+H)).convert('RGBA')
    # darken for contrast
    ov=Image.new('RGBA',(W,H),(18,24,63,110)); im=Image.alpha_composite(im,ov)
    d=ImageDraw.Draw(im)
    # lockup (dark variant) at right
    lock=svg_png(os.path.join(ROOT,'dist','logo','logo-horizontal-dark.svg'), 560)
    im.alpha_composite(lock,(W-560-72, 118))
    # taglines (right aligned)
    draw_text(d,(W-72,318),"تحقّق من نقل الآيات والأحاديث — بلا حكم، بلا توليد", font(40,600), (242,244,255,255))
    d.text((W-72,382),"Verify Quran & Hadith quotations — no judgment, no generation", font=font(26,400), fill=(242,244,255,220), anchor='ra')
    # teal accent bar
    d.rounded_rectangle((W-72-220, 440, W-72, 446), radius=3, fill=(46,242,194,255))
    # footer
    draw_text(d,(W-72,562),"تحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي 2026 · المسار الرابع", font(24,500), (46,242,194,255))
    im=im.convert('RGB')
    im.save(os.path.join(ROOT,'dist','og','og-image.png'), optimize=True)
    im.save(os.path.join(ROOT,'dist','og','og-image.jpg'), quality=86, optimize=True, progressive=True, subsampling=0)

def tw():
    S=600
    bg=Image.open(BG).convert('RGB'); s=S/bg.height; bg=bg.resize((round(bg.width*s),S), Image.LANCZOS)
    x=(bg.width-S)//2; im=bg.crop((x,0,x+S,S)).convert('RGBA')
    im=Image.alpha_composite(im, Image.new('RGBA',(S,S),(18,24,63,120)))
    lock=svg_png(os.path.join(ROOT,'dist','logo','logo-stacked-dark.svg'), 360)
    im.alpha_composite(lock,((S-360)//2, (S-lock.height)//2))
    im.convert('RGB').save(os.path.join(ROOT,'dist','og','twitter-square.jpg'), quality=86, optimize=True, progressive=True)

og(); tw()
for f in ['og-image.jpg','og-image.png','twitter-square.jpg']:
    print(f, os.path.getsize(os.path.join(ROOT,'dist','og',f))//1024,'KB')
