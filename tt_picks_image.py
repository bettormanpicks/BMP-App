#!/usr/bin/env python3
"""
tt_picks_image.py - daily table tennis picks graphic for X (1600x900 PNG).

Only dependency: Pillow  (pip install pillow). Keep the "fonts" folder and
background.png next to this file.

background.png is the backdrop (3D-rendered paddle, ball and net). Replace it
with any 16:9 image to change the look; the title, date, rows and footer are
drawn on top. If it is missing, a simpler drawn paddle and net are used.

COMMAND LINE
    python tt_picks_image.py sample_picks.csv --out picks.png

FROM PYTHON / STREAMLIT (df is the filtered DataFrame behind your table)
    from tt_picks_image import render_picks_png
    png = render_picks_png(df, stats=selected_stats or None)
    st.image(png)
    st.download_button("Download X graphic", png, "tt_picks.png", "image/png")

INPUT
    A CSV, a pandas DataFrame, or a list of dicts, one row per match, with
    Match Start, League, Player 1 and Player 2 columns plus any stat columns.
    The date comes from the Match Start column unless you pass one.

WHICH STATS ARE SHOWN
    stats = a list of column names, shown left to right, one box each.
    When an "X%" column and its "X EF" column are both chosen they share one
    box (percentage on top, EF underneath). Leave stats out (or pass None) to
    get DEFAULT_STATS. About 6-8 boxes reads well; more than that gets small.
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import re
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ───────────────────────── EDIT THESE ─────────────────────────
TITLE_LINE_1 = "THEPONGFATHER'S"
TITLE_LINE_2 = "TABLE TENNIS"
TITLE_ACCENT = "PICKS"  # last word of line 2 (can be colored separately below)
FOOTER_LEFT = "X.COM/BETTORMANPICKS"
FOOTER_RIGHT = "BET RESPONSIBLY"
EF_SUFFIX = "EF"

# Stats shown when none are chosen
DEFAULT_STATS = ["NS%", "1ALL%", "P1 BB%", "P1 BB EF", "P2 BB%", "P2 BB EF",
                 "P1 SR%", "P1 SR EF", "P2 SR%", "P2 SR EF"]
ODDS_SUFFIXES = (" EF", " FO")  # columns shown as odds: +125 / -127

# the columns that identify a match (compared with case/spaces removed)
COLUMNS = {
    "time": ["Match Start", "Time", "Start", "Start Time"],
    "league": ["League", "Lg"],
    "p1": ["P1", "Player 1", "Player1"],
    "p2": ["P2", "Player 2", "Player2"],
    "matchup": ["Matchup", "Match", "Players"],
}

# Colors - matched to the Bettor Man Picks banner (black + neon green + white)
ACCENT = (0, 232, 44)          # box outlines, date pill, rules
ACCENT_HI = (0, 255, 36)       # clock, VS, footer dot
ACCENT_LT = (150, 255, 160)    # labels on green boxes
ACCENT2 = (198, 202, 207)      # outlines of the alternate (silver) boxes
ACCENT2_LT = (238, 240, 242)   # labels on silver boxes
ROW_LINE = (0, 176, 40)        # outline of each match row
TIME_COLOR = (0, 255, 36)
LEAGUE_COLOR = (206, 210, 214)
WHITE = (255, 255, 255)
MUTED = (172, 177, 182)
PANEL_FILL = (17, 17, 17, 236)
BOX_FILL = (5, 5, 5, 242)
PILL_FILL = (9, 9, 9, 245)
FOOTER_COLOR = (226, 229, 232)
_GREEN_TEXT = ((196, 255, 176), (0, 224, 16), (0, 255, 40, 120))    # top, bottom, glow
_WHITE_TEXT = ((255, 255, 255), (186, 192, 198), (255, 255, 255, 60))
LINE1_TOP, LINE1_BOTTOM, LINE1_GLOW = _WHITE_TEXT   # "THEPONGFATHER'S"
LINE2_TOP, LINE2_BOTTOM, LINE2_GLOW = _GREEN_TEXT   # "TABLE TENNIS"
PICKS_TOP, PICKS_BOTTOM, PICKS_GLOW = _GREEN_TEXT   # "PICKS"
TITLE_SHADOW = (0, 0, 0, 240)
BG_TOP, BG_MID, BG_BOTTOM = (21, 21, 21), (25, 25, 25), (9, 9, 9)
BG_GLOW = (0, 255, 40)         # soft glow behind the title and in the lower corners
# ──────────────────────────────────────────────────────────────

BASE_W, BASE_H = 1600, 900
HEADER_H, FOOTER_H = 268, 62
ROW_MAX, ROW_MIN, ROW_GAP = 104, 84, 10
SS = 2  # supersampling factor for smooth edges

FONT_DIR = Path(__file__).resolve().parent / "fonts"
BACKGROUND = Path(__file__).resolve().parent / "background.png"
F_TITLE = "Montserrat-BlackItalic.ttf"
F_ITALIC = "Montserrat-BoldItalic.ttf"
F_XBOLD = "Montserrat-ExtraBold.ttf"
F_BOLD = "Montserrat-Bold.ttf"
F_SEMI = "Montserrat-SemiBold.ttf"

_font_cache: dict = {}


def _font(name: str, size: float) -> ImageFont.FreeTypeFont:
    key = (name, int(round(size)))
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(FONT_DIR / name), key[1])
    return _font_cache[key]


def _fit(name: str, text: str, size: float, max_w: float) -> ImageFont.FreeTypeFont:
    """Largest font at or under `size` whose text fits in max_w."""
    f = _font(name, size)
    while f.getlength(text) > max_w and size > 6:
        size *= 0.96
        f = _font(name, size)
    return f


# ───────────────────────── data handling ─────────────────────────
def _norm(s) -> str:
    # keep % and # so "P1 BB%" and "P1 BB#" stay different columns
    return re.sub(r"[^a-z0-9%#]", "", str(s).lower())


def _blank(v) -> bool:
    return v is None or v != v or str(v).strip() in ("", "nan", "None", "NaN", "-", "--")


def _pct(v, suffix: str = "") -> str:
    if _blank(v):
        return "-"
    try:
        n = float(str(v).replace("%", "").strip())
    except ValueError:
        return str(v).strip()
    txt = f"{n:.0f}" if abs(n - round(n)) < 0.05 else f"{n:.1f}"
    return txt + suffix


def _ef(v) -> str:
    if _blank(v):
        return ""
    s = str(v).replace(EF_SUFFIX, "").replace("−", "-").strip()
    try:
        s = f"{int(round(float(s))):+d}"
    except ValueError:
        pass
    return f"{s} {EF_SUFFIX}".strip()


def _num(v) -> str:
    if _blank(v):
        return "-"
    try:
        n = float(str(v).replace(",", "").strip())
    except ValueError:
        return str(v).strip()
    return f"{n:.0f}" if abs(n - round(n)) < 0.05 else f"{n:.1f}"


def _odds(v) -> str:
    if _blank(v):
        return "-"
    txt = str(v).replace("\u2212", "-").strip()
    try:
        return f"{int(round(float(txt))):+d}"
    except ValueError:
        return txt


def _box_specs(stats, rows) -> list:
    """Column names -> [(label, column, EF column or None)], one per box.
    An "X EF" column is folded into the "X%" box when both are chosen."""
    have = set()
    for m in rows:
        have.update(m["_raw"])
    identity = {_norm(a) for names in COLUMNS.values() for a in names}
    chosen, seen = [], set()
    for c in stats:
        c = str(c).strip()
        n = _norm(c)
        if n in have and n not in identity and n not in seen:
            chosen.append(c)
            seen.add(n)
    pair = {}
    for c in chosen:
        ef = _norm(c[:-1] + " " + EF_SUFFIX)
        if c.endswith("%") and ef in seen:
            pair[_norm(c)] = ef
    folded = set(pair.values())
    specs = []
    for c in chosen:
        n = _norm(c)
        if n in folded:
            continue
        if n in pair:
            specs.append((f"{c[:-1].strip()} %/{EF_SUFFIX}", n, pair[n]))
        else:
            specs.append((c, n, None))
    return specs


def _box_text(label, m, col, ef_col):
    """(main text, text underneath) for one box in one row."""
    v = m["_raw"].get(col)
    if ef_col:
        return _pct(v), _ef(m["_raw"].get(ef_col))
    if label.endswith("%"):
        return _pct(v, "%"), ""
    if label.upper().endswith(ODDS_SUFFIXES):
        return _odds(v), ""
    return _num(v), ""


def _time(v) -> str:
    if hasattr(v, "strftime"):
        return v.strftime("%H:%M")
    if _blank(v):
        return ""
    hit = re.search(r"\d{1,2}:\d{2}", str(v))  # "2026-10-03 11:25" -> "11:25"
    return hit.group(0) if hit else str(v).strip()


def _date_text(d) -> str:
    if d is None:
        d = date.today()
    if isinstance(d, str):
        try:
            d = datetime.strptime(d.strip()[:10], "%Y-%m-%d")
        except ValueError:
            return d  # already formatted, use as typed
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def _date_from_rows(rows):
    """Use the date in the first Match Start value when no date is passed."""
    v = rows[0].get("time")
    if hasattr(v, "year"):
        return v
    hit = re.search(r"\d{4}-\d{2}-\d{2}", str(v))
    return hit.group(0) if hit else None


def _records(matches) -> list:
    if hasattr(matches, "to_dict"):  # pandas DataFrame
        return matches.to_dict("records")
    if isinstance(matches, (str, Path)):
        with open(matches, newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))
    return list(matches)


def _prepare(matches) -> list:
    lookup = {_norm(a): field for field, names in COLUMNS.items() for a in names}
    lookup.update({_norm(field): field for field in COLUMNS})
    rows = []
    for rec in _records(matches):
        m = {"_raw": {_norm(col): val for col, val in rec.items()}}
        for col, val in rec.items():
            field = lookup.get(_norm(col))
            if field and not _blank(val):
                m[field] = val
        if "matchup" in m and ("p1" not in m or "p2" not in m):
            parts = re.split(r"\s+vs?\.?\s+", str(m["matchup"]), maxsplit=1, flags=re.I)
            if len(parts) == 2:
                m["p1"], m["p2"] = parts[0].strip(), parts[1].strip()
        rows.append(m)
    if not rows:
        raise ValueError("No matches to draw.")
    return rows


# ───────────────────────── drawing helpers ─────────────────────────
def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(len(a)))


def _layer(size):
    return Image.new("RGBA", size, (0, 0, 0, 0))


def _gradient_text(img, xy, text, font, top, bottom, anchor="ls"):
    """Draw text filled with a vertical gradient onto img (in place)."""
    x0, y0, x1, y1 = ImageDraw.Draw(img).textbbox(xy, text, font=font, anchor=anchor)
    x0, y0, x1, y1 = int(x0) - 2, int(y0) - 2, int(x1) + 3, int(y1) + 3
    w, h = x1 - x0, y1 - y0
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((xy[0] - x0, xy[1] - y0), text, font=font, fill=255, anchor=anchor)
    grad = Image.new("RGBA", (w, h))
    gd = ImageDraw.Draw(grad)
    for y in range(h):
        gd.line([(0, y), (w, y)], fill=_lerp(top, bottom, y / max(1, h - 1)) + (255,))
    grad.putalpha(mask)
    img.alpha_composite(grad, (x0, y0))


def _tracked_width(text, font, tr):
    return sum(font.getlength(c) for c in text) + tr * (len(text) - 1)


def _draw_tracked(d, x, y, text, font, fill, tr):
    for c in text:
        d.text((x, y), c, font=font, fill=fill, anchor="lm")
        x += font.getlength(c) + tr
    return x


def _background(W, H):
    """Soft background, built at 1x and upscaled by the caller."""
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    top, mid, bot = BG_TOP, BG_MID, BG_BOTTOM
    for y in range(H):
        t = y / (H - 1)
        c = _lerp(top, mid, t / 0.3) if t < 0.3 else _lerp(mid, bot, (t - 0.3) / 0.7)
        d.line([(0, y), (W, y)], fill=c)
    img = img.convert("RGBA")

    glow = _layer((W, H))
    g = ImageDraw.Draw(glow)
    g.ellipse((W / 2 - 640, -150, W / 2 + 640, 300), fill=BG_GLOW + (30,))
    g.ellipse((-260, H - 150, 460, H + 220), fill=BG_GLOW + (20,))
    g.ellipse((W - 460, H - 150, W + 260, H + 220), fill=BG_GLOW + (20,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(110)))

    rnd = random.Random(7)  # fixed seed: same background every day
    bokeh = _layer((W, H))
    b = ImageDraw.Draw(bokeh)
    for _ in range(54):
        x, y = rnd.uniform(0, W), rnd.uniform(-10, 255)
        r, a = rnd.uniform(5, 24), rnd.randint(6, 22)
        b.ellipse((x - r, y - r, x + r, y + r), fill=ACCENT_LT + (a,))
    img.alpha_composite(bokeh.filter(ImageFilter.GaussianBlur(4)))
    return img


def _plate(W, H, k):
    """background.png scaled to the canvas; taller canvases stretch its lower part."""
    p = Image.open(BACKGROUND).convert("RGBA").resize((W * k, BASE_H * k), Image.LANCZOS)
    if H == BASE_H:
        return p
    cut = 600 * k
    out = Image.new("RGBA", (W * k, H * k))
    out.paste(p.crop((0, 0, W * k, cut)), (0, 0))
    out.paste(p.crop((0, cut, W * k, BASE_H * k)).resize((W * k, H * k - cut), Image.BICUBIC), (0, cut))
    return out


def _net(W, k):
    """Table tennis net fading in at the top right."""
    h = HEADER_H
    L = _layer((W * k, h * k))
    d = ImageDraw.Draw(L)
    xl, xr = 1225, W + 12

    def top(x):
        return 80 - (x - xl) / (xr - xl) * 50

    def bot(x):
        return h + (x - xl) / (xr - xl) * 24

    mesh = (205, 208, 212, 84)
    x = xl
    while x <= xr:
        d.line([(x * k, top(x) * k), (x * k, bot(x) * k)], fill=mesh, width=k)
        x += 12
    for i in range(1, 18):
        t = i / 18
        yl = top(xl) + (bot(xl) - top(xl)) * t
        yr = top(xr) + (bot(xr) - top(xr)) * t
        d.line([(xl * k, yl * k), (xr * k, yr * k)], fill=mesh, width=k)
    d.polygon(
        [(xl * k, top(xl) * k), (xr * k, top(xr) * k), (xr * k, (top(xr) + 12) * k), (xl * k, (top(xl) + 8) * k)],
        fill=(236, 243, 255, 225),
    )
    fade = Image.new("L", (W, h), 0)
    fp = fade.load()
    for y in range(h):
        fy = 1.0 if y < 150 else max(0.0, 1 - (y - 150) / (h - 156))
        for x in range(1225, W):
            fx = min(1.0, max(0.0, (x - 1240) / 190))
            fp[x, y] = int(255 * fx * fy)
    fade = fade.resize(L.size, Image.BILINEAR)
    L.putalpha(ImageChops.multiply(L.getchannel("A"), fade))
    return L


def _paddle(k):
    """Red paddle on a square layer, blade centered, rotated into place."""
    S = 620 * k
    c = S / 2
    L = _layer((S, S))
    d = ImageDraw.Draw(L)
    rx, ry = 104 * k, 114 * k
    hw = 29 * k
    hy0, hy1 = c + ry - 16 * k, c + ry + 150 * k
    d.polygon(
        [(c - 60 * k, c + ry - 50 * k), (c + 60 * k, c + ry - 50 * k), (c + hw, hy0 + 40 * k), (c - hw, hy0 + 40 * k)],
        fill=(170, 118, 62),
    )
    d.rounded_rectangle((c - hw, hy0, c + hw, hy1), radius=11 * k, fill=(200, 150, 88))
    d.rectangle((c - hw, hy0, c - hw + 9 * k, hy1 - 11 * k), fill=(146, 97, 48))
    d.rectangle((c + hw - 9 * k, hy0, c + hw, hy1 - 11 * k), fill=(146, 97, 48))
    d.line([(c, hy0 + 44 * k), (c, hy1 - 12 * k)], fill=(120, 78, 38), width=2 * k)
    d.ellipse((c - rx, c - ry, c + rx, c + ry), fill=(104, 12, 20))
    inner = (c - rx + 5 * k, c - ry + 5 * k, c + rx - 5 * k, c + ry - 5 * k)
    d.ellipse(inner, fill=(212, 32, 42))

    hl = _layer((S, S))
    ImageDraw.Draw(hl).ellipse((c - rx * 0.75, c - ry * 0.85, c + rx * 0.25, c - ry * 0.02), fill=(255, 128, 128, 110))
    hl = hl.filter(ImageFilter.GaussianBlur(24 * k))
    blade = Image.new("L", (S, S), 0)
    ImageDraw.Draw(blade).ellipse(inner, fill=255)
    hl.putalpha(ImageChops.multiply(hl.getchannel("A"), blade))
    L.alpha_composite(hl)
    return L.rotate(-48, resample=Image.BICUBIC)


def _ball(k, r=30):
    size = int(r * 2 * k)
    img = _layer((size, size))
    px = img.load()
    hx, hy = size * 0.36, size * 0.32
    for y in range(size):
        for x in range(size):
            dist = ((x - hx) ** 2 + (y - hy) ** 2) ** 0.5 / (size * 0.62)
            s = int(255 - 82 * min(1.0, dist) ** 1.6)
            px[x, y] = (s, s, min(255, s + 5), 255)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    img.putalpha(mask)
    return img


def _place(canvas, sprite, cx, cy, shadow=(0, 0), shadow_blur=0, shadow_alpha=0):
    """Composite sprite centered at (cx, cy); may hang off the canvas."""
    layer = _layer(canvas.size)
    pos = (int(cx - sprite.width / 2), int(cy - sprite.height / 2))
    if shadow_alpha:
        sh = _layer(sprite.size)
        sh.putalpha(sprite.getchannel("A").point(lambda a: int(a * shadow_alpha / 255)))
        sl = _layer(canvas.size)
        sl.paste(sh, (pos[0] + shadow[0], pos[1] + shadow[1]))
        canvas.alpha_composite(sl.filter(ImageFilter.GaussianBlur(shadow_blur)))
    layer.paste(sprite, pos)
    canvas.alpha_composite(layer)


def _clock(d, cx, cy, r, k, color):
    w = max(2, int(round(3.6 * k * r / (24 * k))))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)
    ends = [(cx, cy - r * 0.56), (cx + r * 0.40, cy + r * 0.22)]
    for ex, ey in ends:
        d.line([(cx, cy), (ex, ey)], fill=color, width=w)
        d.ellipse((ex - w / 2, ey - w / 2, ex + w / 2, ey + w / 2), fill=color)
    d.ellipse((cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2), fill=color)


# ───────────────────────── main render ─────────────────────────
def render_picks(matches, picks_date=None, out_path=None, scale: float = 1, stats=None):
    """Render the graphic and return a PIL image. Saves a PNG if out_path is given.

    matches     CSV path, pandas DataFrame, or list of dicts (one per match)
    picks_date  date/datetime, "YYYY-MM-DD", or any text to print as typed.
                Leave it out to use the date in the Match Start column.
    scale       1 = 1600x900 (ideal for X); 2 = 3200x1800
    stats       list of stat column names to show (see top of file); None = DEFAULT_STATS
    """
    rows = _prepare(matches)
    if picks_date is None:
        picks_date = _date_from_rows(rows)
    n = len(rows)
    W = BASE_W
    avail = BASE_H - HEADER_H - FOOTER_H
    cap = ROW_MAX if n >= 5 else ROW_MAX * 1.15  # short slates get slightly taller rows
    row_h = min(cap, (avail - ROW_GAP * (n - 1)) / n)
    if row_h < ROW_MIN:  # too many rows for 16:9 - grow the canvas instead
        row_h = ROW_MIN
        avail = n * row_h + ROW_GAP * (n - 1)
    H = int(HEADER_H + avail + FOOTER_H)
    block = n * row_h + ROW_GAP * (n - 1)
    rows_top = HEADER_H + (avail - block) / 2

    k = int(round(SS * scale))
    P = lambda v: int(round(v * k))  # noqa: E731  base units -> pixels
    size = (W * k, H * k)

    photo = BACKGROUND.exists()
    img = _plate(W, H, k) if photo else _background(W, H).resize(size, Image.BICUBIC)

    # corner accents
    acc = _layer(size)
    a = ImageDraw.Draw(acc)
    for off, alpha, wd in ((0, 210, 3), (16, 120, 2)):
        if not photo:
            a.line([(P(-10), P(128 + off)), (P(128 + off), P(-10))], fill=ACCENT + (alpha,), width=wd * k // 2 + 1)
        a.line([(P(W + 10), P(H - 128 - off)), (P(W - 128 - off), P(H + 10))], fill=ACCENT + (alpha,), width=wd * k // 2 + 1)
    img.alpha_composite(acc)

    if not photo:  # no background.png: fall back to the drawn net, paddle and ball
        img.alpha_composite(_net(W, k))
        _place(img, _paddle(k), P(160), P(104), shadow=(P(8), P(10)), shadow_blur=P(10), shadow_alpha=130)
        _place(img, _ball(k), P(226), P(204), shadow=(P(5), P(7)), shadow_blur=P(7), shadow_alpha=120)

    # ── title ──
    line2 = f"{TITLE_LINE_2} {TITLE_ACCENT}"
    tf = _fit(F_TITLE, line2, 82 * k, 990 * k)
    tf1 = _fit(F_TITLE, TITLE_LINE_1, tf.size, 990 * k)
    cx = P(W / 2 + 8)
    y1, y2 = P(98), P(184)
    w1 = tf1.getlength(TITLE_LINE_1)
    w2a = tf.getlength(TITLE_LINE_2 + " ")
    w2 = w2a + tf.getlength(TITLE_ACCENT)
    x1, x2 = cx - w1 / 2, cx - w2 / 2

    halo = _layer(size)
    hd = ImageDraw.Draw(halo)
    hd.text((x1, y1), TITLE_LINE_1, font=tf1, fill=LINE1_GLOW, anchor="ls")
    hd.text((x2, y2), TITLE_LINE_2, font=tf, fill=LINE2_GLOW, anchor="ls")
    hd.text((x2 + w2a, y2), TITLE_ACCENT, font=tf, fill=PICKS_GLOW, anchor="ls")
    img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(P(13))))
    shadow = _layer(size)
    sd = ImageDraw.Draw(shadow)
    for (tx, ty, txt, f) in ((x1, y1, TITLE_LINE_1, tf1), (x2, y2, line2, tf)):
        sd.text((tx + P(2), ty + P(4)), txt, font=f, fill=TITLE_SHADOW, anchor="ls")
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(P(1.5))))
    _gradient_text(img, (x1, y1), TITLE_LINE_1, tf1, LINE1_TOP, LINE1_BOTTOM)
    _gradient_text(img, (x2, y2), TITLE_LINE_2, tf, LINE2_TOP, LINE2_BOTTOM)
    _gradient_text(img, (x2 + w2a, y2), TITLE_ACCENT, tf, PICKS_TOP, PICKS_BOTTOM)

    # ── date pill ──
    d = ImageDraw.Draw(img)
    dtxt = _date_text(picks_date)
    df = _font(F_ITALIC, 27 * k)
    pw, ph, py = df.getlength(dtxt) + P(84), P(44), P(228)
    px0, px1 = cx - pw / 2, cx + pw / 2
    cut = P(16)
    pill = [(px0 + cut, py - ph / 2), (px1 - cut, py - ph / 2), (px1, py), (px1 - cut, py + ph / 2),
            (px0 + cut, py + ph / 2), (px0, py)]
    d.polygon(pill, fill=PILL_FILL)
    d.line(pill + [pill[0], pill[1]], fill=ACCENT, width=P(2), joint="curve")
    d.text((cx, py), dtxt, font=df, fill=WHITE, anchor="mm")
    line_len = P(250)
    fade = _layer(size)
    fd = ImageDraw.Draw(fade)
    for i in range(line_len):
        al = int(235 * (1 - i / line_len))
        fd.line([(px0 - P(14) - i, py - P(1)), (px0 - P(14) - i, py + P(1))], fill=ACCENT + (al,))
        fd.line([(px1 + P(14) + i, py - P(1)), (px1 + P(14) + i, py + P(1))], fill=ACCENT + (al,))
    img.alpha_composite(fade)

    # ── rows ──
    s = row_h / ROW_MAX  # scale type with row height
    X0, X1 = 32, W - 32
    glow = _layer(size)
    gd = ImageDraw.Draw(glow)
    for i in range(n):
        y0 = rows_top + i * (row_h + ROW_GAP)
        gd.rounded_rectangle((P(X0), P(y0), P(X1), P(y0 + row_h)), radius=P(16), outline=ROW_LINE + (150,), width=P(5))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(P(7))))

    panel = _layer(size)
    d = ImageDraw.Draw(panel)
    f_time = _font(F_XBOLD, 40 * s * k)
    f_league = _font(F_SEMI, 17.5 * s * k)
    f_vs = _font(F_XBOLD, 14 * s * k)

    specs = _box_specs(stats, rows) if stats else []
    if not specs:
        specs = _box_specs(DEFAULT_STATS, rows)
    nb = len(specs)
    area_x0, area_x1, box_gap = 660, X1 - 14, 10
    box_w = min(210, (area_x1 - area_x0 - box_gap * (nb - 1)) / nb) if nb else 0
    box_x0 = area_x0 + (area_x1 - area_x0 - (nb * box_w + box_gap * (nb - 1))) / 2
    texts = [[_box_text(label, m, col, ef) for (label, col, ef) in specs] for m in rows]

    # one value size for the whole graphic, shrunk only if a box is too narrow
    vs = 1.0
    for row_texts in texts:
        for (label, col, ef), (main, _sub) in zip(specs, row_texts):
            base = _font(F_XBOLD, (30 if ef else 35) * s * k)
            vs = min(vs, P(box_w - 16) / max(1.0, base.getlength(main)))
    f_val = _font(F_XBOLD, 30 * s * k * vs)
    f_big = _font(F_XBOLD, 35 * s * k * vs)
    f_ef = _font(F_SEMI, 14 * s * k * max(vs, 0.75))
    label_fonts = [_fit(F_BOLD, label, 13.5 * s * k, P(box_w - 12)) for (label, _c, _e) in specs]

    for i, m in enumerate(rows):
        y0 = rows_top + i * (row_h + ROW_GAP)
        mid = y0 + row_h / 2
        d.rounded_rectangle((P(X0), P(y0), P(X1), P(y0 + row_h)), radius=P(16), fill=PANEL_FILL,
                            outline=ROW_LINE, width=P(2))
        _clock(d, P(X0 + 52), P(mid), P(25 * s), k, ACCENT_HI)
        d.text((P(X0 + 96), P(mid - 11 * s)), _time(m.get("time")), font=f_time, fill=TIME_COLOR, anchor="lm")
        d.text((P(X0 + 98), P(mid + 25 * s)), str(m.get("league", "")), font=f_league, fill=LEAGUE_COLOR, anchor="lm")
        d.line([(P(286), P(y0 + 16 * s)), (P(286), P(y0 + row_h - 16 * s))], fill=ROW_LINE + (170,), width=P(1.5))

        name_cx, name_w = P(473), P(340)
        p1, p2 = str(m.get("p1", "")), str(m.get("p2", ""))
        f_name = _fit(F_BOLD, max((p1, p2), key=len), 25 * s * k, name_w)
        f_name = _fit(F_BOLD, min((p1, p2), key=len), f_name.size, name_w)
        d.text((name_cx, P(mid - 26 * s)), p1, font=f_name, fill=WHITE, anchor="mm")
        d.text((name_cx, P(mid)), "VS", font=f_vs, fill=ACCENT_HI, anchor="mm")
        d.text((name_cx, P(mid + 26 * s)), p2, font=f_name, fill=WHITE, anchor="mm")

        by0, by1 = y0 + 10 * s, y0 + row_h - 10 * s
        for j, (label, col, ef) in enumerate(specs):
            main, sub = texts[i][j]
            bx0 = box_x0 + j * (box_w + box_gap)
            bcx = P(bx0 + box_w / 2)
            line_c, label_c = (ACCENT, ACCENT_LT) if j % 2 == 0 else (ACCENT2, ACCENT2_LT)
            d.rounded_rectangle((P(bx0), P(by0), P(bx0 + box_w), P(by1)), radius=P(11), fill=BOX_FILL,
                                outline=line_c, width=P(2))
            d.text((bcx, P(by0 + 16 * s)), label, font=label_fonts[j], fill=label_c, anchor="mm")
            if ef is None:
                d.text((bcx, P(mid + 9 * s)), main, font=f_big, fill=WHITE, anchor="mm")
            else:
                d.text((bcx, P(mid + 3 * s)), main, font=f_val, fill=WHITE, anchor="mm")
                d.text((bcx, P(by1 - 15 * s)), sub, font=f_ef, fill=MUTED, anchor="mm")
    img.alpha_composite(panel)

    # ── footer ──
    d = ImageDraw.Draw(img)
    ff = _font(F_XBOLD, 22 * k)
    tr = P(3.2)
    fy = P(H - FOOTER_H / 2 + 2)
    sep_w = P(54)
    wl, wr = _tracked_width(FOOTER_LEFT, ff, tr), _tracked_width(FOOTER_RIGHT, ff, tr)
    fx = P(W / 2) - (wl + sep_w + wr) / 2
    foot_c = FOOTER_COLOR
    end = _draw_tracked(d, fx, fy, FOOTER_LEFT, ff, foot_c, tr)
    dot_x, dot_r = fx + wl + sep_w / 2, P(4.5)
    d.ellipse((dot_x - dot_r, fy - dot_r, dot_x + dot_r, fy + dot_r), fill=ACCENT_HI)
    _draw_tracked(d, fx + wl + sep_w, fy, FOOTER_RIGHT, ff, foot_c, tr)
    rule = _layer(size)
    rd = ImageDraw.Draw(rule)
    rl = P(220)
    for i in range(rl):
        al = int(220 * (1 - i / rl))
        rd.line([(fx - P(24) - i, fy - P(1)), (fx - P(24) - i, fy + P(1))], fill=ACCENT + (al,))
        xr = fx + wl + sep_w + wr + P(24) + i
        rd.line([(xr, fy - P(1)), (xr, fy + P(1))], fill=ACCENT + (al,))
    img.alpha_composite(rule)

    out = img.convert("RGB").resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    if out_path:
        out.save(out_path, "PNG", optimize=True)
    return out


def render_picks_png(matches, picks_date=None, scale: float = 1, stats=None) -> bytes:
    """Same as render_picks but returns PNG bytes (handy for st.download_button)."""
    buf = io.BytesIO()
    render_picks(matches, picks_date, scale=scale, stats=stats).save(buf, "PNG", optimize=True)
    return buf.getvalue()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Render the daily table tennis picks graphic.")
    ap.add_argument("csv", help="CSV file with one row per match")
    ap.add_argument("--date", default=None, help='YYYY-MM-DD or any text to print as typed (default: date in Match Start)')
    ap.add_argument("--out", default="tt_picks.png", help="output PNG path")
    ap.add_argument("--scale", type=float, default=1, help="1 = 1600x900, 2 = 3200x1800")
    ap.add_argument("--stats", default=None, help='comma-separated stat columns, e.g. "NS%%,P1 BB%%,P1 BB EF"')
    args = ap.parse_args()
    chosen = [c for c in args.stats.split(",")] if args.stats else None
    im = render_picks(args.csv, args.date, args.out, args.scale, chosen)
    print(f"Saved {args.out} ({im.width}x{im.height})")
