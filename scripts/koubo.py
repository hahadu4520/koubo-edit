"""口播剪辑流水线. Every per-video decision lives in <workdir>/config.json (see config.example.json).

  python koubo.py roughcut <workdir> [--dry]    # transcribe raw, cut pauses + manual cuts -> <id>_粗剪.mp4, report.md
  python koubo.py cues <workdir>                # transcribe rough cut, build subtitle cues -> cues.txt
  python koubo.py find <workdir> 词1 词2 ...     # time of phrases on the rough-cut timeline
  python koubo.py beep <workdir>                # mute + 1kHz beep over config.beeps -> <id>_粗剪_哔.mp4
  python koubo.py preview <workdir> t1 t2 ...   # composite subtitle/花字/list frames at times -> <id>_预览/
  python koubo.py burn <workdir> [--en]         # burn everything -> <id>_成片.mp4 (or _成片_双语.mp4)
  python koubo.py cover <workdir>               # 3:4 covers from config.covers -> <id>_封面/

Run with the skill venv (pillow + jieba): ~/.claude/skills/koubo-edit/venv/bin/python
"""
import json, math, os, re, subprocess, sys, array, wave
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import style as S

PUN = "，。？！、"
GOOD = "的了是就在说把和但呢吗啊么吧"


def sh(*cmd):
    subprocess.run(cmd, check=True)


def load(wd):
    cfg = json.load(open(os.path.join(wd, "config.json")))
    cfg["src"] = os.path.expanduser(cfg["src"])
    cfg.setdefault("id", os.path.splitext(os.path.basename(cfg["src"]))[0].replace("_raw", ""))
    cfg["out_dir"] = os.path.expanduser(cfg.get("out_dir", os.path.dirname(cfg["src"])))
    return cfg


def outp(cfg, suffix):
    return os.path.join(cfg["out_dir"], f"{cfg['id']}{suffix}")


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def transcribe(video, out_json):
    if os.path.exists(out_json):
        return json.load(open(out_json))
    d = os.path.dirname(out_json)
    wav = os.path.join(d, os.path.basename(out_json)[:-5] + ".wav")
    sh("ffmpeg", "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav)
    mw = os.path.join(os.path.dirname(sys.executable), "mlx_whisper")
    sh(mw if os.path.exists(mw) else "mlx_whisper", wav, "--model", "mlx-community/whisper-large-v3-turbo", "--language", "zh",
       "--word-timestamps", "True", "--output-format", "json", "--output-dir", d,
       "--initial-prompt", "以下是普通话的口播，使用简体中文。")
    os.replace(os.path.join(d, os.path.basename(wav)[:-4] + ".json"), out_json)
    return json.load(open(out_json))


def silences(video, noise=-35, dur=0.35):
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", video, "-vn", "-af", f"silencedetect=noise={noise}dB:d={dur}",
                        "-f", "null", "-"], capture_output=True, text=True)
    out = []
    for l in r.stderr.splitlines():
        m = re.search(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", l)
        if m:
            e, d = float(m.group(1)), float(m.group(2)); out.append((e - d, e, d))
    return out


# ---------- 1. rough cut ----------
def cmd_roughcut(wd, *flags):
    cfg = load(wd); src = cfg["src"]; DUR = duration(src)
    raw = transcribe(src, os.path.join(wd, "raw.json"))
    with open(os.path.join(wd, "raw_transcript.txt"), "w") as f:
        for i, s in enumerate(raw["segments"]):
            f.write("%d %.2f-%.2f %s\n" % (i, s["start"], s["end"], s["text"]))
    keep_pre, keep_post = cfg.get("pause_keep", [0.12, 0.10])
    cuts = []
    wav = os.path.join(wd, "raw.wav")
    if not os.path.exists(wav): sh("ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav)
    for s, e, d in silences(wav):
        a, b = s + keep_pre, e - keep_post
        if b - a > 0.12:
            cuts.append((a, b, "停顿 %.1fs" % d))
    cuts += [tuple(c) for c in cfg.get("manual_cuts", [])]
    words = [w for s in raw["segments"] for w in s["words"]]
    if words:
        cuts.append((0, max(0, words[0]["start"] - 0.25), "片头空白"))
        cuts.append((min(DUR, words[-1]["end"] + 0.2), DUR, "片尾空白"))
    cuts.sort()
    m = []
    for a, b, r in cuts:
        if m and a <= m[-1][1]:
            m[-1] = (m[-1][0], max(b, m[-1][1]), m[-1][2] + "+" + r)
        else:
            m.append((a, b, r))
    keep = []; t = 0
    for a, b, r in m:
        if a > t: keep.append((t, a))
        t = max(t, b)
    if t < DUR: keep.append((t, DUR))
    fg = []
    for i, (a, b) in enumerate(keep):
        fg.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}];[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:d=0.01,afade=t=out:st={max(0, b - a - 0.015):.3f}:d=0.015[a{i}]")
    fg.append("".join(f"[v{i}][a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=1[v][a]")
    fgp = os.path.join(wd, "roughcut_filter.txt"); open(fgp, "w").write(";\n".join(fg))
    out = outp(cfg, "_粗剪.mp4")
    if "--dry" not in flags: sh("ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex_script", fgp, "-map", "[v]", "-map", "[a]",
       "-r", "30", "-c:v", "h264_videotoolbox", "-b:v", "14M", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out)
    kept = sum(b - a for a, b in keep)
    with open(os.path.join(wd, "roughcut_report.md"), "w") as f:
        f.write(f"# {cfg['id']} 粗剪\n\n{DUR:.1f}s -> {kept:.1f}s，共 {len(m)} 处剪切\n\n")
        for a, b, r in m:
            if not r.startswith("停顿"):
                f.write(f"- {a:.2f}-{b:.2f} {r}\n")
        f.write(f"- 停顿 {sum(1 for x in m if x[2].startswith('停顿'))} 处\n")
    print(out, "%.1fs -> %.1fs" % (DUR, kept))


# ---------- 2. cues ----------
def build(wd, cfg):
    rough = transcribe(outp(cfg, "_粗剪.mp4"), os.path.join(wd, "rough.json"))
    chars = []
    for s in rough["segments"]:
        for w in s["words"]:
            t = w["word"].strip(); a, b = w["start"], w["end"]
            for i, ch in enumerate(t):
                chars.append([{",": "，", "?": "？"}.get(ch, ch), a + (b - a) * i / max(1, len(t)), b if i == len(t) - 1 else None])
    txt = "".join(c[0] for c in chars)
    for a, b in cfg.get("fix", []):
        while (p := txt.find(a)) >= 0:
            seg = chars[p:p + len(a)]; t0 = seg[0][1]; t1 = seg[-1][2] or seg[-1][1] + 0.15
            chars[p:p + len(a)] = [[ch, t0 + (t1 - t0) * i / len(b), t1 if i == len(b) - 1 else None] for i, ch in enumerate(b)]
            txt = "".join(c[0] for c in chars)
    beeps = cfg.get("beeps", [])
    mask = [any(a - 0.1 <= c[1] <= b + 0.1 and c[0] in w for a, b, w in beeps) for c in chars]
    import jieba
    for w in cfg.get("jieba_words", []): jieba.add_word(w, 10 ** 6)
    phr = []; cur = []
    for i, c in enumerate(chars):
        cur.append(i)
        if c[0] in PUN: phr.append(cur); cur = []
    if cur: phr.append(cur)
    vis = lambda ix: sum(1 for j in ix if chars[j][0] not in PUN)
    maxc = cfg.get("max_chars", 14)
    cues = []
    for ph in phr:
        k = -(-vis(ph) // maxc)
        while k > 1:
            bnd = set(); x = 0
            for w in jieba.cut("".join(chars[j][0] for j in ph)): x += len(w); bnd.add(x)
            target = len(ph) / k; best = None
            for pos in range(3, len(ph) - 3):
                if pos not in bnd: continue
                sc = abs(pos - target) - (1.5 if chars[ph[pos - 1]][0] in GOOD else 0)
                if best is None or sc < best[0]: best = (sc, pos)
            if not best: break
            cues.append(ph[:best[1]]); ph = ph[best[1]:]; k -= 1
        cues.append(ph)
    merged = []
    for cu in cues:
        if merged and (vis(merged[-1]) < 5 or vis(cu) < 4) and vis(merged[-1]) + vis(cu) <= maxc and chars[merged[-1][-1]][0] not in "。？！":
            merged[-1] = merged[-1] + cu
        else:
            merged.append(cu)
    CUES = []
    for idx in merged:
        idx = list(idx)
        while idx and chars[idx[-1]][0] in PUN: idx.pop()
        while idx and chars[idx[0]][0] in PUN: idx.pop(0)
        if idx:
            CUES.append([chars[idx[0]][1], max((chars[j][2] or chars[j][1]) for j in idx) + 0.05, idx])
    for k in range(len(CUES) - 1):
        if CUES[k + 1][0] - CUES[k][1] < 0.6: CUES[k][1] = CUES[k + 1][0]

    def runs_for(c):
        t0, t1, idx = c
        txt = "".join(chars[j][0] for j in idx); st = [None] * len(idx)
        for t, ph, s in cfg.get("highlights", []):
            if t0 - 0.3 <= t <= t1 + 0.3 and (p := txt.find(ph)) >= 0:
                for k in range(p, p + len(ph)): st[k] = s
        for k, j in enumerate(idx):
            if mask[j]: st[k] = "X"
        runs = []
        for j, s in zip(idx, st):
            ch = " " if chars[j][0] in PUN else chars[j][0]
            if runs and runs[-1][1] == s: runs[-1][0] += ch
            else: runs.append([ch, s])
        return [tuple(r) for r in runs]

    with open(os.path.join(wd, "cues.txt"), "w") as f:
        for i, c in enumerate(CUES):
            f.write("%d\t%.2f-%.2f\t%s\n" % (i, c[0], c[1], "".join(r[0] if r[1] != "X" else "■" * len(r[0]) for r in runs_for(c))))
    return CUES, runs_for, chars


def cmd_cues(wd):
    cfg = load(wd); CUES, _, _ = build(wd, cfg)
    print(len(CUES), "cues ->", os.path.join(wd, "cues.txt"))


def cmd_find(wd, *qs):
    cfg = load(wd); _, _, chars = build(wd, cfg)
    txt = "".join(c[0] for c in chars)
    for q in qs:
        p = txt.find(q)
        print(q, "NOT FOUND" if p < 0 else "%.2f-%.2f" % (chars[p][1], chars[p + len(q) - 1][2] or chars[p + len(q) - 1][1]))


# ---------- 3. beep ----------
def cmd_beep(wd):
    cfg = load(wd); src = outp(cfg, "_粗剪.mp4"); out = outp(cfg, "_粗剪_哔.mp4")
    beeps = cfg.get("beeps", [])
    if not beeps:
        sh("cp", src, out); print(out, "(no beeps)"); return
    R = "+".join(f"between(t,{a},{b})" for a, b, _ in beeps)
    sh("ffmpeg", "-y", "-v", "error", "-i", src, "-f", "lavfi", "-i", f"sine=f=1000:sample_rate=44100:d={duration(src) + 1}",
       "-filter_complex", f"[0:a]volume='if({R},0,1)':eval=frame[m];[1:a]volume=0.25,volume='if({R},1,0)':eval=frame,"
       f"aformat=channel_layouts=mono[b];[m][b]amix=inputs=2:duration=first:normalize=0[a]",
       "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out)
    print(out)


# ---------- 4. overlays ----------
def overlays(wd, cfg, en_on):
    CUES, runs_for, _ = build(wd, cfg)
    EN = None
    if en_on:
        EN = json.load(open(os.path.join(wd, "en.json")))
        assert len(EN) == len(CUES), f"en.json has {len(EN)} lines, cues.txt has {len(CUES)}"
    LISTS = [(l["items"], l["reveal"], l["end"]) for l in cfg.get("lists", [])]

    def list_at(t):
        for L, rev, end in LISTS:
            if rev[0] <= t < end:
                return L, L[:sum(1 for r in rev if r <= t)]
        return None, None

    DUR = duration(outp(cfg, "_粗剪.mp4"))
    bps = {0.0, DUR}
    for c in CUES: bps |= {round(c[0], 2), round(c[1], 2)}
    for L, rev, end in LISTS: bps |= set(rev) | {end}
    bps = sorted(b for b in bps if 0 <= b <= DUR)
    OUT = os.path.join(wd, "ov_en" if EN else "ov"); os.makedirs(OUT, exist_ok=True)
    cache = {}; seq = []
    for a, b in zip(bps, bps[1:]):
        if b - a < 0.01: continue
        m = (a + b) / 2
        ci = next((k for k, c in enumerate(CUES) if c[0] <= m < c[1]), None)
        runs = runs_for(CUES[ci]) if ci is not None else None
        en = EN[ci] if (EN and ci is not None) else ""
        full, items = list_at(m)
        key = json.dumps([runs, items, en], ensure_ascii=False)
        if key not in cache:
            img = Image.new("RGBA", (S.W, S.H), (0, 0, 0, 0))
            if runs:
                base = S.BASE
                while True:
                    L = S.line_layer(runs, base)
                    if L.width <= 1000 or base < 48: break
                    base -= 2
                sy = 0.875 if items else 0.76
                img.alpha_composite(L, ((S.W - L.width) // 2, int(S.H * sy - L.height / 2)))
                if en:
                    er = [(t, "X" if i % 2 else None) for i, t in enumerate(re.split(r"\[\[|\]\]", en)) if t]
                    eb = 40
                    while True:
                        E = S.line_layer(er, eb, sw=3)
                        if E.width <= 1020 or eb < 28: break
                        eb -= 2
                    img.alpha_composite(E, ((S.W - E.width) // 2, int(S.H * sy + L.height / 2 - 34)))
            if items:
                B = S.list_block([tuple(x) for x in items], [tuple(x) for x in full])
                img.alpha_composite(B, ((S.W - B.width) // 2, int(S.H * 0.80 - B.height)))
            p = os.path.join(OUT, f"{len(cache):04d}.png"); img.save(p); cache[key] = p
        seq.append((cache[key], a, b))
    lst = os.path.join(wd, "ov_en.txt" if EN else "ov.txt")
    with open(lst, "w") as f:
        f.write("ffconcat version 1.0\n")
        for p, a, b in seq: f.write(f"file '{p}'\nduration {b - a:.3f}\n")
        f.write(f"file '{seq[-1][0]}'\n")
    return seq, lst


def cmd_preview(wd, *ts):
    cfg = load(wd); en = "--en" in ts; ts = [float(t) for t in ts if t != "--en"]
    seq, _ = overlays(wd, cfg, en)
    od = outp(cfg, "_双语预览" if en else "_预览"); os.makedirs(od, exist_ok=True)
    src = outp(cfg, "_粗剪_哔.mp4") if os.path.exists(outp(cfg, "_粗剪_哔.mp4")) else outp(cfg, "_粗剪.mp4")
    outs = []
    for T in ts:
        f = next(p for p, a, b in seq if a <= T < b)
        tmp = os.path.join(wd, "_frame.png")
        sh("ffmpeg", "-v", "error", "-y", "-ss", str(T), "-i", src, "-frames:v", "1", tmp)
        im = Image.open(tmp).convert("RGBA").resize((S.W, S.H)); im.alpha_composite(Image.open(f))
        mm, ss = divmod(T, 60); p = os.path.join(od, f"{int(mm)}m{ss:04.1f}s.jpg"); im.convert("RGB").save(p, quality=90); outs.append(p)
    w, h, cols = 272, 480, 5
    c = Image.new("RGB", (cols * w, -(-len(outs) // cols) * h))
    for i, f in enumerate(outs): c.paste(Image.open(f).resize((w, h)), ((i % cols) * w, (i // cols) * h))
    c.save(os.path.join(od, "00_总览.jpg"), quality=88)
    print(od)


def cmd_burn(wd, *flags):
    cfg = load(wd); en = "--en" in flags
    _, lst = overlays(wd, cfg, en)
    src = outp(cfg, "_粗剪_哔.mp4") if os.path.exists(outp(cfg, "_粗剪_哔.mp4")) else outp(cfg, "_粗剪.mp4")
    out = outp(cfg, "_成片_双语.mp4" if en else "_成片.mp4")
    sh("ffmpeg", "-y", "-v", "error", "-i", src, "-f", "concat", "-safe", "0", "-i", lst, "-filter_complex",
       f"[1:v]fps=30,format=rgba,scale={S.W}:{S.H}[o];[0:v][o]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]",
       "-map", "[v]", "-map", "0:a", "-c:v", "h264_videotoolbox", "-b:v", "14M", "-c:a", "copy", "-movflags", "+faststart", out)
    print(out)


# ---------- 5. cover ----------
SERIF = os.path.join(S.FONTS, "NotoSerifCJKsc-Black.otf")
BRUSH = os.path.join(S.FONTS, "MaShanZheng-Regular.ttf")
GOLD = "#FFD84A"


def title(text, fontp, size, track=0.08, gold=""):
    f = ImageFont.truetype(fontp, size)
    adv = [f.getlength(c) for c in text]
    tw = int(sum(adv) + size * track * (len(text) - 1)); pad = 60
    gi = set(range(text.find(gold), text.find(gold) + len(gold))) if gold and gold in text else set()
    im = Image.new("RGBA", (tw + 2 * pad, int(size * 1.35) + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im); x = pad
    for i, c in enumerate(text):
        d.text((x, pad + size), c, font=f, fill=GOLD if i in gi else S.WH, anchor="ls", stroke_width=2, stroke_fill=(30, 30, 30))
        x += adv[i] + size * track
    a = im.split()[3]
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    glow.putalpha(a.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.85)))
    out = Image.new("RGBA", im.size, (0, 0, 0, 0)); out.alpha_composite(glow, (0, 6)); out.alpha_composite(im)
    return out.crop(out.getbbox())


def cmd_cover(wd):
    cfg = load(wd); cv = cfg["cover"]; od = outp(cfg, "_封面"); os.makedirs(od, exist_ok=True)
    src = outp(cfg, "_粗剪.mp4"); l1, l2 = cv["lines"]; gold = cv.get("gold", "")
    st1, st2 = cv.get("stagger", [l1, l2])
    for n, fr in enumerate(cv["frames"], 1):
        tmp = os.path.join(wd, "_cover.png")
        sh("ffmpeg", "-v", "error", "-y", "-ss", str(fr["t"]), "-i", src, "-frames:v", "1", tmp)
        im0 = Image.open(tmp).convert("RGB"); cw = fr.get("cw", 900); ch = int(cw * 4 / 3)
        x0 = max(0, min(im0.width - cw, fr["cx"] - cw // 2)); y0 = max(0, min(im0.height - ch, int(fr["eye"] - fr.get("at", 0.5) * ch)))
        im = im0.crop((x0, y0, x0 + cw, y0 + ch)).resize((1080, 1440), Image.LANCZOS)
        im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.05)).enhance(1.04).convert("RGBA")
        put = lambda L, x, y: im.alpha_composite(L, (int((1080 - L.width) // 2 if x == "c" else (x if x >= 0 else 1080 + x - L.width)), int(y)))
        lay = fr.get("layout", "stack")
        if lay == "stack":
            put(title(l1, SERIF, 130, 0.06, gold), "c", 50); put(title(l2, SERIF, 190, 0.6), "c", 230)
        elif lay == "brush":
            put(title(l1, SERIF, 110, 0.12), "c", 40); put(title(l2, BRUSH, 220, 0.3), "c", 175)
        else:
            put(title(st1, SERIF, 130, 0.05, gold), 70, 40); put(title(st2, SERIF, 130, 0.05), -70, 200)
        p = os.path.join(od, f"封面{n}_{lay}_{fr['t']}s.jpg"); im.convert("RGB").save(p, quality=94); print(p)


if __name__ == "__main__":
    cmd, wd, *rest = sys.argv[1:]
    globals()["cmd_" + cmd](os.path.abspath(os.path.expanduser(wd)), *rest)
