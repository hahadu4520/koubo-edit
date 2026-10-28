"""House 花字 style: subtitle runs (A/B/C1/C2/H/X) and 得意黑 numbered lists."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")

# 字幕黑体：Mac 冬青黑体 W6 → Windows 微软雅黑 Bold → Linux 思源黑体
SUBF = next(((p, i) for p, i in [("/System/Library/Fonts/Hiragino Sans GB.ttc", 2),
                                 (os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "msyhbd.ttc"), 0),
                                 ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2)] if os.path.exists(p)),
            ("/System/Library/Fonts/Hiragino Sans GB.ttc", 2))
W, H = 1088, 1920
Y = "#FFD400"; R = "#FF3B30"; CY = "#4FD1FF"; WH = "#FFFFFF"; BK = "#000000"
BASE, SHEAR = 68, 0.22

# inline styles: (colour, scale, italic, underline, stroke colour)
ST = {
    None: (WH, 1.0, False, False, BK),
    "A":  (Y, 1.10, True, False, BK),
    "B":  (R, 1.15, True, False, WH),
    "C1": (Y, 1.10, True, False, BK),
    "C2": (CY, 1.10, True, False, BK),
    "U":  (WH, 1.10, False, True, BK),
    "H":  (Y, 1.35, True, False, BK),
    "X":  (WH, 1.0, False, False, BK),
}



def font(sz): return ImageFont.truetype(SUBF[0], sz, index=SUBF[1])

def shadowed(out):
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    sh.putalpha(out.split()[3].point(lambda a: a * 0.5).filter(ImageFilter.GaussianBlur(4)))
    fin = Image.new("RGBA", (out.width + 8, out.height + 8), (0, 0, 0, 0))
    fin.alpha_composite(sh, (3, 5)); fin.alpha_composite(out, (0, 0))
    return fin

def line_layer(runs, base, sw=4):
    """One line; styled runs share a baseline, italic runs are slanted around it."""
    big = int(base * 1.35)
    asc = font(big).getmetrics()[0]
    th = asc + int(big * 0.4) + 2 * (sw + 12)
    by = sw + 12 + asc
    pieces = []
    for text, key in runs:
        col, sc, ital, under, stroke = ST[key]
        f = font(int(base * sc))
        w = int(f.getlength(text)) + 2 * sw + 4
        extra = int(SHEAR * th) if ital else 0
        im = Image.new("RGBA", (w + extra, th), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.text((sw + 2, by), text, font=f, fill=col, anchor="ls",
               stroke_width=sw + (1 if key else 0), stroke_fill=stroke)
        if under:
            uy = by + int(base * 0.16)
            d.rectangle((sw + 2, uy - sw, w - 2, uy + 6 + sw), fill=BK)
            d.rectangle((sw + 2 + sw, uy, w - 2 - sw, uy + 6), fill=col)
        if ital:
            im = im.transform(im.size, Image.AFFINE, (1, SHEAR, -SHEAR * by, 0, 1, 0), Image.BICUBIC)
            if stroke == WH:  # dark ring outside a white stroke
                ring = Image.new("RGBA", im.size, (0, 0, 0, 0))
                ring.putalpha(im.split()[3].filter(ImageFilter.MaxFilter(5)))
                ring.alpha_composite(im); im = ring
        if key == 'X':
            bb0 = im.getbbox(); pw, ph = bb0[2]-bb0[0], bb0[3]-bb0[1]
            blk = Image.new('RGBA', (pw + 12, int(base*1.05)), (90, 90, 96, 255))
            tx = im.crop(bb0).resize((max(1, pw//14), max(1, ph//14)), Image.BILINEAR).resize((pw, ph), Image.NEAREST)
            blk.alpha_composite(tx, (6, (blk.height-ph)//2))
            blk = blk.resize((max(1,blk.width//10), max(1,blk.height//10)), Image.BILINEAR).resize(blk.size, Image.NEAREST)
            im = Image.new('RGBA', im.size, (0,0,0,0)); im.alpha_composite(blk, (sw, by - int(base*0.92)))
        bb = im.getbbox()
        pieces.append(im.crop((bb[0], 0, bb[2], th)))
    GAP = -8
    tw = sum(p.width for p in pieces) + GAP * (len(pieces) - 1)
    out = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    x = 0
    for p in pieces:
        out.alpha_composite(p, (x, 0)); x += p.width + GAP
    return shadowed(out)

HUAF = os.path.join(FONTS, "SmileySans-Oblique.ttf")  # 得意黑

def list_block(items, full, size=76):
    """Left-aligned numbered list in 得意黑 with a hard offset shadow, laid out against the full list."""
    f = ImageFont.truetype(HUAF, size)
    lh = int(size * 1.22)
    sw, hard = 6, 6
    bw = int(max(f.getlength(n + " " + t) for n, t in full)) + 2 * (sw + hard) + 30
    out = Image.new("RGBA", (bw, lh * len(full) + 2 * (sw + hard) + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    for k, (n, t) in enumerate(items):
        y = sw + 10 + k * lh
        xt = sw + 10 + f.getlength(n + " ")
        for dx, dy, solid in ((hard, hard, BK), (0, 0, None)):
            d.text((sw + 10 + dx, y + dy), n, font=f, fill=solid or Y, stroke_width=sw, stroke_fill=BK)
            d.text((xt + dx, y + dy), t, font=f, fill=solid or WH, stroke_width=sw, stroke_fill=BK)
    return shadowed(out)

