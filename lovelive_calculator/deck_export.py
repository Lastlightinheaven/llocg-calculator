"""
Generate a deck-sheet PNG image from the current editor state.

Layout:
  ┌──────────────────────────────────────────────────────┐
  │  Header: title + stats                               │
  ├────────────────────────────┬─────────────────────────┤
  │  Card grid (type → cost)   │  Trigger table          │
  │                            │  Cost bar chart         │
  └────────────────────────────┴─────────────────────────┘
"""
from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_ASSETS    = Path(__file__).parent / "Assets"
_FONT_PATH = _ASSETS / "Fonts" / "rounded-x-mplus-2c-medium.ttf"
_FONT_THAI = _ASSETS / "Fonts" / "NotoSansThai.ttf"  # Noto Sans Thai รองรับ Thai
_CARD_BACK = _ASSETS / "Images" / "card_back.png"

# Scale factor — 2 = 2× resolution
_SCALE = 2

_THUMB_W   = 110 * _SCALE
_THUMB_H   = 154 * _SCALE
_GRID_COLS = 6

# Color palette
_BG       = (22,  8,  40)
_BG2      = (38, 14,  58)
_BG3      = (28, 12,  48)
_PINK     = (233, 30, 140)
_PURPLE   = (107, 45, 107)
_TEXT     = (240, 230, 255)
_TEXT_SUB = (196, 168, 212)
_OK       = (100, 220, 120)
_WARN     = (255, 179,  71)
_WHITE    = (255, 255, 255)
_BLACK    = (  0,   0,   0)

_TRIG_COLOR: Dict[str, Tuple[int,int,int]] = {
    "red":    (220,  60,  60),
    "blue":   ( 70, 140, 230),
    "green":  ( 50, 200,  90),
    "yellow": (220, 190,  40),
    "purple": (170,  90, 230),
    "pink":   (233,  30, 140),
    "all":    (200, 200, 200),
}
_TRIG_LABEL = {
    "red": "แดง", "blue": "น้ำเงิน", "green": "เขียว",
    "yellow": "เหลือง", "purple": "ม่วง", "pink": "ชมพู", "all": "All",
}

_COST_BINS: List[Tuple[str, int, int]] = [
    ("1-3",  1,  3), ("4",   4,  4), ("5-8",  5,  8),
    ("9",    9,  9), ("10-11",10,11), ("12-15",12,15), ("16+",16,999),
]
_BIN_COLORS: List[Tuple[int,int,int]] = [
    (244,114,182),(233,30,140),(196,23,122),
    (160,23,106),(124,58,237),(91,33,182),(59,7,100),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _font(size: int, thai: bool = False) -> ImageFont.FreeTypeFont:
    path = _FONT_THAI if (thai and _FONT_THAI.exists()) else _FONT_PATH
    try:
        return ImageFont.truetype(str(path), size * _SCALE)
    except Exception:
        return ImageFont.load_default()


def _rr(draw: ImageDraw.ImageDraw, xy, r, fill=None, outline=None, lw=1):
    draw.rounded_rectangle(list(xy), radius=r, fill=fill, outline=outline, width=lw)


def _tc(draw: ImageDraw.ImageDraw, cx, cy, text, font, fill):
    bb = font.getbbox(text)
    w, h = bb[2]-bb[0], bb[3]-bb[1]
    draw.text((cx - w//2, cy - h//2 - bb[1]), text, font=font, fill=fill)


_thumb_cache: Dict[str, Image.Image] = {}

# Live card เป็น landscape (489×350) — ขนาดให้พอดี 4 ใบใน GRID_W (6 cols × member width)
# GRID_W = 6*(THUMB_W+PAD)+PAD+MARGIN = 6*(220+10)+10+28 = 1418; 4 ใบ+5 gap = 4W+50 ≤ 1418 → W ≤ 342
_LIVE_THUMB_W = 330  # px (scale=2 included) — วาง 4 ใบพอดีใน grid
_LIVE_THUMB_H = round(_LIVE_THUMB_W * 350 / 489)

def _thumb(path: str | None, is_live: bool = False) -> Image.Image:
    cache_key = (path or "") + ("_live" if is_live else "")
    if cache_key in _thumb_cache:
        return _thumb_cache[cache_key]
    tw = _LIVE_THUMB_W if is_live else _THUMB_W
    th = _LIVE_THUMB_H if is_live else _THUMB_H
    try:
        img = Image.open(path).convert("RGBA").resize((tw, th), Image.LANCZOS)
    except Exception:
        try:
            img = Image.open(_CARD_BACK).convert("RGBA").resize((tw, th), Image.LANCZOS)
        except Exception:
            img = Image.new("RGBA", (tw, th), _BG2)
    _thumb_cache[cache_key] = img
    return img


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------
def _draw_header(canvas, draw, title, total, n_member, n_live, n_blades, width) -> int:
    H = 68 * _SCALE
    draw.rectangle([0, 0, width, H], fill=_BG2)
    # pink accent line bottom
    draw.rectangle([0, H - 3*_SCALE, width, H], fill=_PINK)

    f_title = _font(18)
    f_stat  = _font(12)

    draw.text((16*_SCALE, 14*_SCALE), title or "Deck Sheet", font=f_title, fill=_WHITE)

    stats = [
        (f"{total} / 60 pcs", _OK   if total    == 60 else _WARN),
        (f"Member : {n_member}",  _OK   if n_member == 48 else _WARN),
        (f"Live : {n_live}",      _OK   if n_live   == 12 else _WARN),
        (f"Blades : {n_blades}",  _TEXT_SUB),
    ]
    x = width - 16*_SCALE
    for txt, col in reversed(stats):
        bb = f_stat.getbbox(txt)
        tw = bb[2]-bb[0]
        draw.text((x - tw, 28*_SCALE), txt, font=f_stat, fill=col)
        x -= tw + 20*_SCALE

    return H + 8*_SCALE


def _draw_card_grid(canvas, draw, groups, left, top) -> int:
    PAD     = 5  * _SCALE
    LABEL_H = 20 * _SCALE
    CB      = 18 * _SCALE
    f_grp   = _font(11)
    f_cnt   = _font(10)

    y = top
    for group_label, items in groups:
        draw.text((left + PAD, y + 2*_SCALE), group_label, font=f_grp, fill=_PINK)
        y += LABEL_H

        is_live_group = any(
            (c.card_type == "live") for c, _ in items if c
        )
        tw = _LIVE_THUMB_W if is_live_group else _THUMB_W
        th = _LIVE_THUMB_H if is_live_group else _THUMB_H

        col = 0
        for card, entry in items:
            x = left + PAD + col * (tw + PAD)
            t = _thumb(card.image if card else None, is_live=is_live_group)
            mask = Image.new("L", (tw, th), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                [0, 0, tw-1, th-1], radius=6*_SCALE, fill=255)
            canvas.paste(t, (x, y), mask)

            # count badge
            cnt = entry["count"]
            bx0 = x + tw - CB - 2*_SCALE
            by0 = y + th - CB - 2*_SCALE
            draw.rectangle([bx0, by0, bx0+CB, by0+CB], fill=(0,0,0,210))
            _tc(draw, bx0+CB//2, by0+CB//2, str(cnt), f_cnt, _WHITE)

            col += 1
            if col >= _GRID_COLS:
                col = 0
                y += th + PAD

        if col > 0:
            y += th + PAD
        y += 4*_SCALE

    return y


def _draw_trigger_table(draw, trig_counts, all_val, non_val, sp_val,
                        left, top, width) -> int:
    """Draw trigger as a clean 2-column table (label | count)."""
    f_title = _font(11, thai=True)
    f_row   = _font(12, thai=True)

    draw.text((left, top), "Trigger ใน Deck", font=f_title, fill=_TEXT_SUB)
    top += 18 * _SCALE

    ROW_H   = 26 * _SCALE
    PAD_X   =  8 * _SCALE
    BAR_MAX = width - PAD_X * 2
    CIRCLE_R = 6 * _SCALE

    rows = [
        (k, _TRIG_COLOR[k], _TRIG_LABEL[k], trig_counts.get(k, 0))
        for k in ("red","blue","green","yellow","purple","pink","all")
    ]
    rows += [
        ("non",    _TEXT_SUB, "Non-Trigger", non_val),
    ]
    if sp_val > 0:
        rows += [("sp", (0, 210, 200), "Score+", sp_val)]

    total_triggers = sum(r[3] for r in rows)

    for key, color, label, val in rows:
        alpha = 255 if val > 0 else 80
        c = (*color[:3], alpha)

        # color dot
        cx, cy = left + CIRCLE_R + PAD_X, top + ROW_H // 2
        draw.ellipse([cx-CIRCLE_R, cy-CIRCLE_R, cx+CIRCLE_R, cy+CIRCLE_R], fill=c)

        # label
        draw.text((cx + CIRCLE_R + PAD_X, top + ROW_H//2 - _font(12).getbbox("A")[3]//2 - 2),
                  label, font=f_row, fill=(*_TEXT[:3], alpha))

        # count (right side)
        val_str = str(val)
        vbb = f_row.getbbox(val_str)
        vw = vbb[2]-vbb[0]
        draw.text((left + width - PAD_X - vw, top + ROW_H//2 - vbb[3]//2 - 2),
                  val_str, font=f_row,
                  fill=(*color[:3], alpha) if val > 0 else (*_TEXT_SUB, 80))

        # mini progress bar
        if total_triggers > 0 and val > 0:
            bar_y = top + ROW_H - 3*_SCALE
            bar_len = int(BAR_MAX * val / total_triggers)
            draw.rectangle([left + PAD_X, bar_y,
                            left + PAD_X + bar_len, bar_y + 2*_SCALE],
                           fill=(*color[:3], 160))

        top += ROW_H

    return top + 8*_SCALE


def _draw_cost_chart(draw, bin_counts, left, top, width) -> int:
    f_title = _font(11)
    f_lbl   = _font(10)
    f_val   = _font(10)

    top += 6*_SCALE
    draw.text((left, top), "Cost Distribution", font=f_title, fill=_TEXT_SUB)
    top += 22*_SCALE

    VAL_LABEL_H = 18 * _SCALE  # พื้นที่สำหรับ value label เหนือ bar
    X_LABEL_H   = 18 * _SCALE  # พื้นที่สำหรับ x-axis label ใต้ bar
    BAR_H_MAX   = 110 * _SCALE # ความสูงสูงสุดของ bar area
    GAP         =   5 * _SCALE
    n           = len(_COST_BINS)
    bar_w       = (width - GAP*(n+1)) // n
    max_val     = max((bin_counts.get(l,0) for l,_,_ in _COST_BINS), default=1) or 1

    bar_top = top + VAL_LABEL_H  # bar เริ่มต้นใต้ value label area
    bar_bot = bar_top + BAR_H_MAX

    for i, ((label,_,__), color) in enumerate(zip(_COST_BINS, _BIN_COLORS)):
        val = bin_counts.get(label, 0)
        bx  = left + GAP + i*(bar_w+GAP)
        bh  = max(int(BAR_H_MAX * val / max_val), 2*_SCALE) if val else 2*_SCALE
        by  = bar_bot - bh

        alpha = 255 if val > 0 else 50
        _rr(draw, (bx, by, bx+bar_w, bar_bot),
            r=3*_SCALE, fill=(*color, alpha))

        # value label เหนือ bar — อยู่ใน VAL_LABEL_H zone เสมอ
        if val > 0:
            vbb = f_val.getbbox(str(val))
            vw, vh = vbb[2]-vbb[0], vbb[3]-vbb[1]
            vy = max(top, by - vh - 4*_SCALE)
            draw.text((bx + bar_w//2 - vw//2, vy), str(val), font=f_val, fill=_WHITE)

        # x-axis label ใต้ bar
        lbb = f_lbl.getbbox(label)
        lw  = lbb[2]-lbb[0]
        draw.text((bx + bar_w//2 - lw//2, bar_bot + 4*_SCALE),
                  label, font=f_lbl, fill=_TEXT_SUB)

    return bar_bot + X_LABEL_H + 10*_SCALE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_deck_png(
    entries: List[dict],
    card_index: dict,
    live_cards: list,
    title: str = "",
    lookup_fn=None,
    strip_fn=None,
) -> bytes:
    def _lookup(cn):
        if lookup_fn:
            return lookup_fn(cn)
        c = card_index.get(cn)
        if c is None and strip_fn:
            c = card_index.get(strip_fn(cn))
        return c

    # ── gather data ────────────────────────────────────────────
    type_order = {"member":0,"live":1,"energy":2,"":9}
    type_label = {"member":"Member","live":"Live","energy":"Energy","":"Unknown"}

    groups_raw: Dict[str,list] = {}
    total_cards = n_member = n_live = 0
    trig_counts: Dict[str,int] = {}
    non_trig = sp_count = 0
    bin_counts: Dict[str,int] = {l:0 for l,_,__ in _COST_BINS}
    live_lut = {c.card_no: c for c in live_cards}

    for e in entries:
        card = _lookup(e["card_no"])
        cnt  = e["count"]
        total_cards += cnt
        t = card.card_type if card else ""
        if t == "member": n_member += cnt
        if t == "live":   n_live   += cnt
        groups_raw.setdefault(t, []).append((card, e))

        tc  = card.trigger_color if card else None
        key = tc.value if tc else None
        if key and key in _TRIG_COLOR:
            trig_counts[key] = trig_counts.get(key,0) + cnt
        else:
            non_trig += cnt

        if card:
            lc = live_lut.get(card.card_no) or (
                live_lut.get(strip_fn(card.card_no)) if strip_fn else None)
            if lc and lc.score_plus > 0:
                sp_count += cnt

        if card and card.cost > 0:
            for lbl, lo, hi in _COST_BINS:
                if lo <= card.cost <= hi:
                    bin_counts[lbl] += cnt
                    break

    non_val = non_trig - sp_count
    all_val = trig_counts.get("all", 0)

    groups: List[Tuple[str,list]] = []
    for t in sorted(groups_raw, key=lambda x: type_order.get(x,9)):
        items = sorted(groups_raw[t], key=lambda x: (x[0].cost if x[0] else 999))
        groups.append((type_label.get(t,t), items))

    n_blades = sum(
        (getattr(card,"blade",0)) * e["count"]
        for e in entries
        if (card := _lookup(e["card_no"]))
    )

    # ── canvas sizing ──────────────────────────────────────────
    MARGIN  = 14 * _SCALE
    PAD     = 10 * _SCALE
    GRID_W  = _GRID_COLS * (_THUMB_W + 5*_SCALE) + 5*_SCALE + MARGIN
    INFO_W  = 300 * _SCALE
    CANVAS_W = GRID_W + INFO_W + MARGIN * 3

    HEADER_H = 68 * _SCALE + 8*_SCALE
    # คำนวณ GRID_H โดยคิด Live row สูงน้อยกว่า Member
    GRID_H = 0
    for grp_label, items in groups:
        is_live_grp = any(c.card_type == "live" for c, _ in items if c)
        th = _LIVE_THUMB_H if is_live_grp else _THUMB_H
        rows = math.ceil(len(items) / _GRID_COLS)
        GRID_H += rows * (th + 5*_SCALE) + 24*_SCALE
    GRID_H += 20*_SCALE
    n_groups = len(groups)

    # estimate info panel height
    INFO_H = (18+26*9+8 + 18+80+10 + 40) * _SCALE

    CANVAS_H = HEADER_H + max(GRID_H, INFO_H) + MARGIN * 2

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), _BG)
    draw   = ImageDraw.Draw(canvas, "RGBA")

    # ── header ─────────────────────────────────────────────────
    y_body = _draw_header(canvas, draw, title, total_cards,
                          n_member, n_live, n_blades, CANVAS_W)

    # ── card grid ──────────────────────────────────────────────
    _draw_card_grid(canvas, draw, groups,
                    left=MARGIN, top=y_body)

    # ── right panel ────────────────────────────────────────────
    rx = GRID_W + MARGIN
    rw = INFO_W
    # subtle panel background
    draw.rectangle([rx - PAD//2, y_body,
                    rx + rw + PAD//2, CANVAS_H - MARGIN], fill=_BG2)
    _rr(draw, (rx - PAD//2, y_body,
               rx + rw + PAD//2, CANVAS_H - MARGIN),
        r=8*_SCALE, outline=_PURPLE, lw=_SCALE)

    ry = y_body + PAD

    ry = _draw_trigger_table(
        draw, trig_counts, all_val, non_val, sp_count,
        left=rx, top=ry, width=rw,
    )

    # divider
    draw.rectangle([rx, ry, rx+rw, ry+_SCALE], fill=_PURPLE)
    ry += 8*_SCALE

    _draw_cost_chart(draw, bin_counts,
                     left=rx, top=ry, width=rw)

    # ── export ─────────────────────────────────────────────────
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
