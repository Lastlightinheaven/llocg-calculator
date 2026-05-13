"""
Deck Editor — สร้าง/แก้ไข deck แล้ว sync กลับไปยัง Calculator หลัก.

Layout (2 columns):
  Left  (40%) : Filter panel + card browser (grid)
  Right (60%) : Deck list (ปรับจำนวน / ลบ) + summary bar + Apply button
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Path bootstrap — ต้องการเพื่อ import modules จาก lovelive_calculator/
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).parent          # pages/
_APP_DIR  = _THIS_DIR.parent              # lovelive_calculator/
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from models import Color, COLOR_EMOJI, COLOR_LABELS_TH, DeckComposition
from card_db import DeckCard, get_card_index, get_live_cards, strip_rarity_suffix
from deck_import import DeckEntry, compose_deck_from_entries
from deck_export import generate_deck_png
from card_db import fetch_and_save_card_text_th

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Deck Editor — LLOCG",
    page_icon="✏️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Shared CSS (same dark theme tokens as main app)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@400;500;600;700;800&family=Noto+Sans:wght@400;500;600;700;800&display=swap');
:root {
    --llocg-pink:      #e91e8c;
    --llocg-pink-dark: #c4177a;
    --llocg-pink-light:#4a1535;
    --llocg-text:      #f0e6ff;
    --llocg-text-sub:  #c4a8d4;
    --llocg-card:      #2d1040;
    --llocg-border:    #6b2d6b;
    --llocg-shadow:    0 2px 12px rgba(233,30,140,0.2);
}
html, body { font-family: 'Noto Sans Thai', 'Noto Sans', sans-serif !important; }
h1 {
    font-weight: 800 !important; color: #fff !important;
    background: var(--llocg-pink) !important;
    padding: 0.55em 1.2em !important; border-radius: 0 0 16px 16px !important;
    margin-bottom: 1em !important; box-shadow: var(--llocg-shadow) !important;
}
h2 { font-weight: 700 !important; color: var(--llocg-pink) !important; border-bottom: 2px solid var(--llocg-border) !important; padding-bottom: 0.3em !important; }
h3 { font-weight: 700 !important; color: var(--llocg-pink) !important; }

div[data-testid="stButton"] > button {
    background: var(--llocg-pink) !important; color: #fff !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 700 !important; padding: 0.45em 1.4em !important;
    box-shadow: 0 2px 8px rgba(233,30,140,0.4) !important;
}
div[data-testid="stButton"] > button:hover { background: var(--llocg-pink-dark) !important; }

div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] div[data-baseweb="select"] {
    background: #1a0a2e !important; color: var(--llocg-text) !important;
    border-color: var(--llocg-border) !important;
}
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label, label[data-testid] {
    visibility: visible !important; width: auto !important;
    overflow: visible !important; height: auto !important; opacity: 1 !important;
}

/* Card tile in browser */
.card-tile {
    border: 2px solid var(--llocg-border);
    border-radius: 10px;
    overflow: hidden;
    cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s;
    background: var(--llocg-card);
    margin-bottom: 4px;
}
.card-tile:hover { border-color: var(--llocg-pink); box-shadow: var(--llocg-shadow); }
.card-tile-label {
    font-size: 0.68rem; text-align: center;
    color: var(--llocg-text-sub); padding: 2px 4px 4px; line-height: 1.3;
}

/* Deck list row */
.deck-row {
    display: flex; align-items: center; gap: 6px;
    background: var(--llocg-card); border: 1px solid var(--llocg-border);
    border-radius: 8px; padding: 6px 10px; margin-bottom: 4px;
}
.deck-row-name { flex: 1; font-size: 0.82rem; color: var(--llocg-text); }
.deck-row-count {
    font-size: 1rem; font-weight: 700;
    color: var(--llocg-pink); min-width: 1.8em; text-align: center;
}

/* Card hover preview */
.card-preview-wrap {
    position: relative;
    display: inline-block;
    width: 100%;
}
.card-preview-popup {
    display: none;
    position: absolute;
    left: 80%;
    top: 50%;
    transform: translateY(-50%);
    margin-left: 10px;
    width: 208px;
    background: #1a0a2e;
    border: 2px solid var(--llocg-pink);
    border-radius: 12px;
    box-shadow: 0 6px 24px rgba(233,30,140,0.5);
    z-index: 9999;
    overflow: hidden;
    pointer-events: none;
}
.card-preview-popup img { width: 100%; display: block; }
.card-preview-wrap:hover .card-preview-popup { display: block; }



/* Summary bar */
.summary-bar {
    background: var(--llocg-card); border: 1.5px solid var(--llocg-border);
    border-radius: 10px; padding: 0.7rem 1rem; margin-bottom: 0.7rem;
    display: flex; gap: 1.5rem; align-items: center;
}
.summary-total { font-size: 1.4rem; font-weight: 800; color: var(--llocg-pink); }
.summary-warn  { color: #ffb347; font-weight: 700; font-size: 0.9rem; }
.summary-ok    { color: #7fff7f; font-weight: 700; font-size: 0.9rem; }

/* Trigger summary grid */
.trigger-grid {
    background: var(--llocg-card); border: 1.5px solid var(--llocg-border);
    border-radius: 10px; padding: 0.6rem 0.9rem; margin-bottom: 0.6rem;
}
.trigger-grid-title {
    font-size: 0.78rem; font-weight: 700; color: var(--llocg-text-sub);
    text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.45rem;
}
.trigger-chips { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.tc { display: inline-flex; align-items: center; gap: 0.25rem;
      background: #1a0a2e; border: 1.5px solid var(--llocg-border);
      border-radius: 6px; padding: 2px 8px; font-size: 0.82rem; font-weight: 700; }
.tc-zero { opacity: 0.35; }
.tc-val { color: var(--llocg-pink); min-width: 1.4em; text-align: right; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _card_img_src(image: str) -> str:
    """Cache base64-encoded images globally — encode once per process lifetime."""
    if not image:
        return ""
    if image.startswith("http://") or image.startswith("https://"):
        return image
    p = Path(image)
    if not p.is_absolute():
        p = _APP_DIR / p
    if not p.exists():
        return ""
    data = base64.b64encode(p.read_bytes()).decode()
    suffix = p.suffix.lower().lstrip(".")
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
    return f"data:{mime};base64,{data}"


def _ensure_card_db_loaded() -> None:
    if "live_cards" not in st.session_state:
        cards, source = get_live_cards(force_refresh=False)
        st.session_state.live_cards = cards
        st.session_state.live_cards_source = source
    if "card_index" not in st.session_state:
        idx, source = get_card_index(force_refresh=False)
        st.session_state.card_index = idx
        st.session_state.card_index_source = source


def _apply_deck_composition(dc: DeckComposition) -> None:
    # เก็บใน _deck_comp (non-widget) — ไม่ถูก Streamlit reset เมื่อเปลี่ยนหน้า
    st.session_state["_deck_comp"] = {
        "red":       dc.trigger_counts.get(Color.RED, 0),
        "blue":      dc.trigger_counts.get(Color.BLUE, 0),
        "green":     dc.trigger_counts.get(Color.GREEN, 0),
        "yellow":    dc.trigger_counts.get(Color.YELLOW, 0),
        "purple":    dc.trigger_counts.get(Color.PURPLE, 0),
        "pink":      dc.trigger_counts.get(Color.PINK, 0),
        "all":       dc.all_trigger,
        "non_plain": dc.non_trigger - dc.score_plus_count,
        "sp":        dc.score_plus_count,
    }
    # ล้าง hand/WR keys เพื่อให้ app.py fingerprint ใหม่แล้วสร้าง widgets ใหม่
    for _k in list(st.session_state.keys()):
        if _k.startswith("wr_hand_n_") or _k.startswith("wr_extra_n_"):
            del st.session_state[_k]
    st.session_state.pop("wr_hand_n", None)
    st.session_state.pop("wr_extra_n", None)


def _lookup_card(card_no: str) -> DeckCard | None:
    """Lookup card by card_no with strip_rarity_suffix fallback."""
    idx: dict = st.session_state.get("card_index", {})
    return idx.get(card_no) or idx.get(strip_rarity_suffix(card_no))


def _get_all_deck_cards() -> list[DeckCard]:
    """Return unique DeckCard list from card_index (dedup by card_no)."""
    idx: dict = st.session_state.get("card_index", {})
    seen: set = set()
    cards: list[DeckCard] = []
    for card in idx.values():
        if card.card_no not in seen:
            seen.add(card.card_no)
            cards.append(card)
    return cards


def _render_decklog_export(entries: list[dict], total_cards: int) -> None:
    """ส่วน Export ไป Decklog — POST จาก server ตรงไปยัง Decklog API (ไม่ต้องติดตั้งอะไร)."""
    from decklog_publish import publish_deck_to_decklog, DecklogPublishError

    st.markdown("### 📤 ส่งไป Decklog")

    default_title = st.session_state.get("imported_title", "") or "My Deck"
    deck_title = st.text_input(
        "ชื่อ Deck",
        value=st.session_state.get("_decklog_title_input", default_title),
        placeholder="ใส่ชื่อ Deck ที่จะแสดงบน Decklog",
        key="_decklog_title_input",
    )

    export_disabled = total_cards == 0
    if st.button(
        "📤 ส่งไป Decklog",
        use_container_width=True,
        disabled=export_disabled,
        help="สร้าง Deck ใหม่บน Decklog ทันที — ได้ลิงก์กลับมาพร้อมใช้",
        type="primary",
    ):
        title = deck_title.strip() or default_title
        with st.spinner("กำลังสร้าง Deck บน Decklog..."):
            try:
                result = publish_deck_to_decklog(entries, title=title)
                st.session_state["_decklog_result"] = result
            except DecklogPublishError as e:
                st.session_state["_decklog_result"] = str(e)

    result = st.session_state.get("_decklog_result")
    if result is not None:
        from decklog_publish import PublishResult
        if isinstance(result, PublishResult):
            st.success(f"✅ สร้าง Deck สำเร็จ! Deck Code: **{result.deck_id}**")
            st.markdown(
                f'<a href="{result.url}" target="_blank" '
                f'style="display:inline-block;background:#e91e8c;color:#fff;padding:10px 22px;'
                f'border-radius:8px;font-weight:700;text-decoration:none;font-size:0.95rem;'
                f'box-shadow:0 2px 8px rgba(233,30,140,0.4);">'
                f'🔗 เปิด Deck บน Decklog</a>',
                unsafe_allow_html=True,
            )
        else:
            st.error(f"เกิดข้อผิดพลาด: {result}")


# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
_ensure_card_db_loaded()

# editor_entries: list[dict]  — {"card_no": str, "count": int}
if "editor_entries" not in st.session_state:
    # seed from imported_entries if available
    imported = st.session_state.get("imported_entries") or []
    st.session_state.editor_entries = [
        {"card_no": e.card_no, "count": e.count} for e in imported
    ]

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown("# ✏️ Deck Editor")
st.caption("สร้างหรือแก้ไข Deck — กด Apply เพื่อส่งกลับ Calculator หลัก")

# ---------------------------------------------------------------------------
# Layout: Left = browser, Right = deck list
# ---------------------------------------------------------------------------
col_browser, col_deck = st.columns([4, 3], gap="large")

# ============================================================
# LEFT — Card Browser
# ============================================================
with col_browser:
    st.markdown("## 🔍 เลือกการ์ด")

    # ── Filter controls ──────────────────────────────────────
    with st.container():
        search = st.text_input("ค้นหาชื่อการ์ด", placeholder="ชื่อการ์ด / card no", key="editor_search")

        all_cards = _get_all_deck_cards()

        # Card type
        type_options = ["ทั้งหมด", "member", "live", "energy"]
        type_labels  = {"ทั้งหมด": "ทั้งหมด", "member": "🎭 Member", "live": "🎵 Live", "energy": "🔋 Energy"}
        sel_type = st.selectbox(
            "ประเภทการ์ด",
            options=type_options,
            format_func=lambda x: type_labels.get(x, x),
            key="editor_filter_type",
        )

        # Group (series)
        groups = sorted({c.series for c in all_cards if c.series})
        sel_group = st.selectbox(
            "กลุ่ม (Series)",
            options=["ทั้งหมด"] + groups,
            key="editor_filter_group",
        )

        # Unit
        units = sorted({c.unit for c in all_cards if c.unit})
        sel_unit = st.selectbox(
            "ยูนิต",
            options=["ทั้งหมด"] + units,
            key="editor_filter_unit",
        )

        # Cost range
        all_costs = [c.cost for c in all_cards]
        cost_min_global = min(all_costs) if all_costs else 0
        cost_max_global = max(all_costs) if all_costs else 22
        cost_range = st.slider(
            "ค่าคอส",
            min_value=cost_min_global,
            max_value=cost_max_global,
            value=(cost_min_global, cost_max_global),
            key="editor_filter_cost",
        )

    st.markdown("---")

    # ── Apply filters ─────────────────────────────────────────
    filtered: list[DeckCard] = []
    sq = search.strip().lower()
    for card in all_cards:
        if sel_type != "ทั้งหมด" and card.card_type != sel_type:
            continue
        if sel_group != "ทั้งหมด" and card.series != sel_group:
            continue
        if sel_unit != "ทั้งหมด" and card.unit != sel_unit:
            continue
        if not (cost_range[0] <= card.cost <= cost_range[1]):
            continue
        if sq and sq not in card.name.lower() and sq not in card.card_no.lower():
            continue
        filtered.append(card)

    # sort: type order then card_no
    _TYPE_ORDER = {"member": 0, "live": 1, "energy": 2}
    filtered.sort(key=lambda c: (_TYPE_ORDER.get(c.card_type, 9), c.card_no))

    # ── Pagination ────────────────────────────────────────────
    PAGE_SIZE = 30
    GRID_COLS = 5
    CARD_W    = 120

    total_filtered = len(filtered)
    total_pages    = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)

    # reset page when filter changes
    filter_sig = (search, sel_type, sel_group, sel_unit, cost_range)
    if st.session_state.get("_editor_filter_sig") != filter_sig:
        st.session_state["_editor_filter_sig"] = filter_sig
        st.session_state["_editor_page"] = 0

    cur_page = st.session_state.get("_editor_page", 0)
    cur_page = max(0, min(cur_page, total_pages - 1))

    page_start = cur_page * PAGE_SIZE
    page_cards = filtered[page_start : page_start + PAGE_SIZE]

    st.caption(f"แสดง {page_start+1}–{page_start+len(page_cards)} จาก {total_filtered:,} การ์ด (หน้า {cur_page+1}/{total_pages})")

    # ── Card detail panel (locked on click) ──────────────────
    _sel = st.session_state.get("_selected_card_no")
    _sel_card: DeckCard | None = _lookup_card(_sel) if _sel else None
    if _sel_card:
        _panel_src  = _card_img_src(_sel_card.image) if _sel_card.image else ""
        _panel_text = (_sel_card.text_th or "").replace("<", "《").replace(">", "》").replace("\n", "<br>")
        _type_label = {"member": "🎭 Member", "live": "🎵 Live", "energy": "🔋 Energy"}.get(_sel_card.card_type, _sel_card.card_type)
        _tc_badge   = COLOR_EMOJI.get(_sel_card.trigger_color, "⬛") if _sel_card.trigger_color else "⬛"
        _cost_str   = f"💎 {_sel_card.cost}" if _sel_card.cost else "—"
        _blade_str  = f"⚔️ {_sel_card.blade}" if _sel_card.blade else ""
        _is_live = _sel_card.card_type == "live"
        _img_w   = "180px" if not _is_live else "260px"
        _panel_img_tag  = f'<img src="{_panel_src}" style="width:{_img_w};display:block;flex-shrink:0;border-radius:10px 0 0 10px;">' if _panel_src else ""
        _panel_text_div = (
            f'<div style="font-size:1.06rem;color:#f0e6ff;line-height:1.7;'
            f'padding:8px 12px 12px;border-top:1px solid #6b2d6b;">{_panel_text}</div>'
        ) if _panel_text else ""
        _panel_blade = f"&nbsp;·&nbsp;{_blade_str}" if _blade_str else ""
        st.markdown(
            f'<div style="background:#2d1040;border:2px solid #e91e8c;border-radius:12px;'
            f'margin-bottom:10px;overflow:hidden;display:flex;align-items:stretch;">'
            f'{_panel_img_tag}'
            f'<div style="flex:1;min-width:0;display:flex;flex-direction:column;">'
            f'<div style="padding:10px 12px 6px;">'
            f'<div style="font-size:0.92rem;font-weight:700;color:#f0e6ff;margin-bottom:2px;">{_sel_card.name}</div>'
            f'<div style="font-size:0.72rem;color:#c4a8d4;margin-bottom:4px;">{_sel_card.card_no}</div>'
            f'<div style="font-size:0.76rem;color:#c4a8d4;">'
            f'{_type_label} &nbsp;·&nbsp; {_tc_badge} &nbsp;·&nbsp; {_cost_str}{_panel_blade}'
            f'</div></div>'
            f'{_panel_text_div}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("✕ ปิด", key="close_card_panel", use_container_width=False):
            st.session_state.pop("_selected_card_no", None)
            st.rerun()

    st.markdown("---")

    # ── Card grid (current page only) ─────────────────────────
    def _get_editor_counts() -> dict[str, int]:
        return {e["card_no"]: e["count"] for e in st.session_state.editor_entries}

    def _add_card(card_no: str) -> None:
        entries = st.session_state.editor_entries
        for e in entries:
            if e["card_no"] == card_no:
                e["count"] = min(e["count"] + 1, 50)
                return
        entries.append({"card_no": card_no, "count": 1})

    _GRID_COLS_LIVE   = 3
    _CARD_W_LIVE      = 220
    _GRID_COLS_MEMBER = GRID_COLS   # 5
    _CARD_W_MEMBER    = CARD_W      # 120

    ec = _get_editor_counts()

    # แยก live / non-live ก่อน แล้ว loop แต่ละกลุ่มอิสระ
    live_cards_page    = [c for c in page_cards if c.card_type == "live"]
    nonlive_cards_page = [c for c in page_cards if c.card_type != "live"]

    def _render_card(card: DeckCard, card_w: int) -> None:
        src = _card_img_src(card.image) if card.image else ""
        tc = card.trigger_color
        badge = COLOR_EMOJI.get(tc, "⬛") if tc else "⬛"
        in_deck = ec.get(card.card_no, 0)
        is_selected = st.session_state.get("_selected_card_no") == card.card_no
        border = "3px solid #e91e8c" if (in_deck or is_selected) else "2px solid #6b2d6b"
        bg = "#3d1858" if is_selected else "#2d1040"
        if src:
            _img_html = f'<img src="{src}" style="width:100%;display:block;">'
        else:
            _img_html = (
                f'<div style="height:80px;display:flex;align-items:center;'
                f'justify-content:center;color:#c4a8d4;font-size:0.65rem;'
                f'padding:4px;text-align:center;">{card.card_no}</div>'
            )
        _short_name = card.name[:18] + ("…" if len(card.name) > 18 else "")
        _count_html = f'<br><b style="color:#e91e8c">×{in_deck}</b>' if in_deck else ""
        st.markdown(
            f'<div style="border:{border};border-radius:10px;overflow:hidden;'
            f'background:{bg};margin-bottom:2px;max-width:{card_w}px;'
            f'margin-left:auto;margin-right:auto;">'
            f'{_img_html}'
            f'<div style="font-size:0.62rem;text-align:center;color:#c4a8d4;'
            f'padding:2px 3px 4px;line-height:1.2;">'
            f'{badge} {_short_name}{_count_html}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button(
                "🔍",
                key=f"sel_{card.card_no}_{cur_page}",
                use_container_width=True,
                help="ดูรายละเอียด",
                type="primary" if is_selected else "secondary",
            ):
                if is_selected:
                    st.session_state.pop("_selected_card_no", None)
                else:
                    st.session_state["_selected_card_no"] = card.card_no
                st.rerun()
        with c2:
            if st.button("＋", key=f"add_{card.card_no}_{cur_page}", use_container_width=True, help="เพิ่มเข้า Deck"):
                _add_card(card.card_no)
                st.rerun()

    for row_start in range(0, len(live_cards_page), _GRID_COLS_LIVE):
        row = live_cards_page[row_start : row_start + _GRID_COLS_LIVE]
        cols = st.columns(_GRID_COLS_LIVE)
        for j, card in enumerate(row):
            with cols[j]:
                _render_card(card, _CARD_W_LIVE)

    for row_start in range(0, len(nonlive_cards_page), _GRID_COLS_MEMBER):
        row = nonlive_cards_page[row_start : row_start + _GRID_COLS_MEMBER]
        cols = st.columns(_GRID_COLS_MEMBER)
        for j, card in enumerate(row):
            with cols[j]:
                _render_card(card, _CARD_W_MEMBER)

    # ── Pagination nav (ด้านล่าง grid) ───────────────────────
    pn_cols = st.columns([1, 1, 3, 1, 1])
    with pn_cols[0]:
        if st.button("⏮", disabled=(cur_page == 0), key="pg_first"):
            st.session_state["_editor_page"] = 0
            st.rerun()
    with pn_cols[1]:
        if st.button("◀", disabled=(cur_page == 0), key="pg_prev"):
            st.session_state["_editor_page"] = cur_page - 1
            st.rerun()
    with pn_cols[3]:
        if st.button("▶", disabled=(cur_page >= total_pages - 1), key="pg_next"):
            st.session_state["_editor_page"] = cur_page + 1
            st.rerun()
    with pn_cols[4]:
        if st.button("⏭", disabled=(cur_page >= total_pages - 1), key="pg_last"):
            st.session_state["_editor_page"] = total_pages - 1
            st.rerun()

# ============================================================
# RIGHT — Deck List
# ============================================================
with col_deck:
    st.markdown("## 📋 Deck ปัจจุบัน")

    entries: list[dict] = st.session_state.editor_entries
    idx: dict = st.session_state.get("card_index", {})

    # ── Summary bar ───────────────────────────────────────────
    total_cards  = sum(e["count"] for e in entries)
    total_member = sum(
        e["count"] for e in entries
        if (_lookup_card(e["card_no"]) or type("", (), {"card_type": ""})()).card_type == "member"
    )
    total_live = sum(
        e["count"] for e in entries
        if (_lookup_card(e["card_no"]) or type("", (), {"card_type": ""})()).card_type == "live"
    )

    def _rule_status(actual: int, expected: int, label: str) -> str:
        if actual == expected:
            return f'<span class="summary-ok">✅ {label} {actual}</span>'
        return f'<span class="summary-warn">⚠️ {label} {actual}/{expected}</span>'

    diff = total_cards - 60
    if diff == 0:
        total_status = '<span class="summary-ok">✅ 60 ใบ</span>'
    elif diff > 0:
        total_status = f'<span class="summary-warn">⚠️ เกิน ({diff:+d})</span>'
    else:
        total_status = f'<span class="summary-warn">⚠️ ขาด {-diff} ใบ</span>'

    st.markdown(
        f'<div class="summary-bar" style="flex-wrap:wrap;gap:0.8rem;">'
        f'<span class="summary-total">{total_cards} / 60</span>'
        f'{total_status}'
        f'&nbsp;|&nbsp;'
        f'{_rule_status(total_member, 48, "🎭 Member")}'
        f'&nbsp;·&nbsp;'
        f'{_rule_status(total_live, 12, "🎵 Live")}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Rule violations ───────────────────────────────────────
    rule_errors = []
    if total_cards != 60:
        rule_errors.append(f"Deck ต้องมีพอดี 60 ใบ (ปัจจุบัน {total_cards} ใบ)")
    if total_member != 48:
        rule_errors.append(f"Member ต้องมีพอดี 48 ใบ (ปัจจุบัน {total_member} ใบ)")
    if total_live != 12:
        rule_errors.append(f"Live ต้องมีพอดี 12 ใบ (ปัจจุบัน {total_live} ใบ)")

    # ── Trigger summary ───────────────────────────────────────
    _trig_counts: dict[Color | str, int] = {}
    _non_trig = 0
    _sp_count = 0
    live_lut = {c.card_no: c for c in st.session_state.get("live_cards", [])}
    for e in entries:
        card = _lookup_card(e["card_no"])
        if card is None:
            _non_trig += e["count"]
            continue
        tc = card.trigger_color
        if tc in (Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW, Color.PURPLE, Color.PINK):
            _trig_counts[tc] = _trig_counts.get(tc, 0) + e["count"]
        elif tc == Color.ALL:
            _trig_counts[Color.ALL] = _trig_counts.get(Color.ALL, 0) + e["count"]
        else:
            _non_trig += e["count"]
        lc = live_lut.get(card.card_no) or live_lut.get(strip_rarity_suffix(card.card_no))
        if lc and lc.score_plus > 0:
            _sp_count += e["count"]

    _color_chips = [
        (Color.RED,    COLOR_EMOJI[Color.RED],    "แดง"),
        (Color.BLUE,   COLOR_EMOJI[Color.BLUE],   "น้ำเงิน"),
        (Color.GREEN,  COLOR_EMOJI[Color.GREEN],  "เขียว"),
        (Color.YELLOW, COLOR_EMOJI[Color.YELLOW], "เหลือง"),
        (Color.PURPLE, COLOR_EMOJI[Color.PURPLE], "ม่วง"),
        (Color.PINK,   COLOR_EMOJI[Color.PINK],   "ชมพู"),
    ]
    _all_val  = _trig_counts.get(Color.ALL, 0)
    _non_val  = _non_trig - _sp_count

    def _chip(emoji: str, label: str, val: int) -> str:
        zero_cls = " tc-zero" if val == 0 else ""
        return (f'<span class="tc{zero_cls}">'
                f'{emoji} {label} <span class="tc-val">{val}</span></span>')

    chips_html = "".join(
        _chip(emoji, label, _trig_counts.get(color, 0))
        for color, emoji, label in _color_chips
    )
    chips_html += _chip(COLOR_EMOJI[Color.ALL], "All", _all_val)
    chips_html += _chip("⬛", "Non", _non_val)
    if _sp_count > 0:
        chips_html += _chip("⭐", "Score+", _sp_count)

    st.markdown(
        f'<div class="trigger-grid">'
        f'<div class="trigger-grid-title">Trigger ใน Deck</div>'
        f'<div class="trigger-chips">{chips_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Cost distribution chart ────────────────────────────────
    if entries:
        import altair as alt

        _COST_BINS = [
            ("1-3",  1,  3),
            ("4",    4,  4),
            ("5-8",  5,  8),
            ("9",    9,  9),
            ("10-11",10, 11),
            ("12-15",12, 15),
            ("16+",  16, 999),
        ]
        # สีไล่ระดับตาม Cost (ต่ำ→สูง: pink→purple→deep)
        _BIN_COLORS = ["#f472b6", "#e91e8c", "#c4177a", "#a0106a", "#7c3aed", "#5b21b6", "#3b0764"]

        bin_counts: dict[str, int] = {label: 0 for label, _, _ in _COST_BINS}
        for e in entries:
            card = _lookup_card(e["card_no"])
            c = card.cost if card else 0
            if c <= 0:
                continue
            for label, lo, hi in _COST_BINS:
                if lo <= c <= hi:
                    bin_counts[label] += e["count"]
                    break

        bin_order = [label for label, _, _ in _COST_BINS]
        chart_data = [
            {"Cost": label, "จำนวน": bin_counts[label], "สี": color}
            for (label, _, _), color in zip(_COST_BINS, _BIN_COLORS)
        ]

        max_val = max((d["จำนวน"] for d in chart_data), default=1)

        bars = (
            alt.Chart(alt.Data(values=chart_data))
            .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
            .encode(
                x=alt.X("Cost:N", sort=bin_order,
                        axis=alt.Axis(labelColor="#c4a8d4", labelFontSize=12,
                                      titleColor="#9d7bb0", titleFontSize=12,
                                      domainColor="#6b2d6b", tickColor="#6b2d6b")),
                y=alt.Y("จำนวน:Q",
                        scale=alt.Scale(domain=[0, max(max_val + 2, 6)]),
                        axis=alt.Axis(labelColor="#c4a8d4", labelFontSize=11,
                                      titleColor="#9d7bb0", titleFontSize=12,
                                      gridColor="#3a1a5a", domainColor="#6b2d6b",
                                      tickColor="#6b2d6b", tickMinStep=1)),
                color=alt.Color("สี:N", scale=None, legend=None),
                tooltip=[
                    alt.Tooltip("Cost:N", title="Cost Range"),
                    alt.Tooltip("จำนวน:Q", title="จำนวนการ์ด"),
                ],
            )
        )

        labels = (
            alt.Chart(alt.Data(values=chart_data))
            .mark_text(dy=-8, fontSize=12, fontWeight="bold", color="#f0e6ff")
            .encode(
                x=alt.X("Cost:N", sort=bin_order),
                y=alt.Y("จำนวน:Q"),
                text=alt.Text("จำนวน:Q"),
            )
        )

        chart = (
            (bars + labels)
            .properties(
                title=alt.TitleParams("Cost Distribution", color="#c4a8d4",
                                      fontSize=13, fontWeight="bold", anchor="start"),
                height=200,
                background="transparent",
                padding={"left": 8, "right": 8, "top": 8, "bottom": 4},
            )
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart, use_container_width=True)

    # ── Import from Decklog button ─────────────────────────────
    if st.button("📥 โหลดจาก Deck ที่ Import แล้ว", use_container_width=True):
        imported = st.session_state.get("imported_entries") or []
        if imported:
            st.session_state.editor_entries = [
                {"card_no": e.card_no, "count": e.count} for e in imported
            ]
            st.rerun()
        else:
            st.warning("ยังไม่ได้ Import Deck จาก Decklog — ไปที่หน้าหลักก่อน")

    if st.button("🗑️ ล้าง Deck ทั้งหมด", use_container_width=True):
        st.session_state.editor_entries = []
        st.rerun()

    st.markdown("---")

    # ── Deck entry list ───────────────────────────────────────
    if not entries:
        st.info("Deck ว่างเปล่า — กด ＋ เพิ่ม การ์ดจากแถบซ้าย")
    else:
        # Group by type for display
        type_order_label = {"member": "🎭 Member", "live": "🎵 Live", "energy": "🔋 Energy", "": "❓ Unknown"}
        type_order_key   = {"member": 0, "live": 1, "energy": 2, "": 9}

        groups_display: dict[str, list[dict]] = {}
        for e in entries:
            card = _lookup_card(e["card_no"])
            t = card.card_type if card else ""
            groups_display.setdefault(t, []).append((card, e))

        for t in sorted(groups_display, key=lambda x: type_order_key.get(x, 9)):
            items = groups_display[t]
            # sort by cost ascending, unknown cost last
            items.sort(key=lambda x: (x[0].cost if x[0] else 999))
            group_total = sum(e["count"] for _, e in items)
            st.markdown(f"**{type_order_label.get(t, t)}** — {group_total} ใบ")

            for card, e in items:
                card_no = e["card_no"]
                count   = e["count"]
                name    = card.name if card else card_no
                tc      = card.trigger_color if card else None
                badge   = COLOR_EMOJI.get(tc, "⬛") if tc else "⬛"
                cost    = card.cost if card else 0
                cost_str = f"Cost {cost}" if (card and cost > 0) else ""
                img_src = _card_img_src(card.image) if (card and card.image) else ""
                text_th = (card.text_th if card else "") or ""
                # build tooltip: รูป + text (ถ้ามี)
                text_th_escaped = text_th.replace("<", "《").replace(">", "》").replace('"', "&quot;").replace("\n", "<br>")
                text_html = (
                    f'<div style="font-size:0.72rem;color:#f0e6ff;padding:5px 7px 6px;'
                    f'line-height:1.5;border-top:1px solid #6b2d6b;">{text_th_escaped}</div>'
                    if text_th else ""
                )
                _img_tag = f'<img src="{img_src}" style="width:100%;display:block;">' if img_src else ""
                popup_html_full = (
                    f'<div class="card-preview-popup">{_img_tag}{text_html}</div>'
                ) if (img_src or text_th) else ""

                c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 1])
                with c1:
                    st.markdown(
                        f'<div class="card-preview-wrap">'
                        f'<div style="font-size:0.8rem;color:#f0e6ff;padding:6px 0;">'
                        f'{badge} {name}<br>'
                        f'<span style="font-size:0.68rem;color:#c4a8d4;">{card_no}</span>'
                        f'</div>'
                        f'{popup_html_full}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with c2:
                    st.markdown(
                        f'<div style="font-size:0.78rem;font-weight:700;color:#c4a8d4;'
                        f'text-align:center;padding-top:10px;">'
                        f'{"💎 " + str(cost) if cost_str else "—"}</div>',
                        unsafe_allow_html=True,
                    )
                with c3:
                    st.markdown(
                        f'<div style="font-size:1rem;font-weight:800;color:#e91e8c;'
                        f'text-align:center;padding-top:8px;">×{count}</div>',
                        unsafe_allow_html=True,
                    )
                with c4:
                    if st.button("－", key=f"dec_{card_no}"):
                        if count > 1:
                            e["count"] = count - 1
                        else:
                            st.session_state.editor_entries = [
                                x for x in st.session_state.editor_entries
                                if x["card_no"] != card_no
                            ]
                        st.rerun()
                with c5:
                    if st.button("＋", key=f"inc_{card_no}"):
                        e["count"] = min(count + 1, 50)
                        st.rerun()

    st.markdown("---")

    # ── Apply button ──────────────────────────────────────────
    if rule_errors:
        for err in rule_errors:
            st.warning(f"⚠️ {err}")

    apply_disabled = total_cards == 0 or bool(rule_errors)
    if st.button(
        "✅ Apply — ส่งกลับ Calculator",
        use_container_width=True,
        disabled=apply_disabled,
        type="primary",
    ):
        entries_objs = [
            DeckEntry(card_no=e["card_no"], count=e["count"])
            for e in st.session_state.editor_entries
        ]
        card_index = st.session_state.get("card_index", {})
        live_cards = st.session_state.get("live_cards", [])
        dc, warnings = compose_deck_from_entries(entries_objs, card_index, live_cards)
        _apply_deck_composition(dc)
        st.session_state.imported_entries = entries_objs
        st.session_state.imported_source  = "editor"
        st.session_state.imported_title   = "Deck Editor"
        if warnings:
            for w in warnings:
                st.warning(w)
        if rule_errors:
            st.warning("⚠️ Apply สำเร็จ แต่ Deck ยังไม่ถูกกฎ — ตรวจสอบจำนวนการ์ดอีกครั้ง")
        else:
            st.success(f"✅ Apply สำเร็จ! Deck {total_cards} ใบ (Member 48 / Live 12) — กลับหน้าหลักได้เลย")

    # ── Export PNG ────────────────────────────────────────────
    st.markdown("---")
    export_disabled = total_cards == 0
    if st.button(
        "🖼️ Export รูป Deck Sheet",
        use_container_width=True,
        disabled=export_disabled,
        help="สร้างรูป PNG สรุป Deck พร้อม Trigger และ Cost Distribution",
    ):
        with st.spinner("กำลังสร้างรูป..."):
            try:
                _card_index = st.session_state.get("card_index", {})
                _live_cards = st.session_state.get("live_cards", [])
                _title = st.session_state.get("imported_title", "") or "My Deck"
                png_bytes = generate_deck_png(
                    entries=st.session_state.editor_entries,
                    card_index=_card_index,
                    live_cards=_live_cards,
                    title=_title,
                    lookup_fn=_lookup_card,
                    strip_fn=strip_rarity_suffix,
                )
                st.session_state["_export_png"] = png_bytes
            except Exception as ex:
                st.error(f"เกิดข้อผิดพลาด: {ex}")

    if st.session_state.get("_export_png"):
        _png = st.session_state["_export_png"]
        st.download_button(
            label="⬇️ ดาวน์โหลด PNG",
            data=_png,
            file_name="deck_sheet.png",
            mime="image/png",
            use_container_width=True,
        )
        st.image(_png, caption="Preview", use_container_width=True)

    # ── Export to Decklog ─────────────────────────────────────
    st.markdown("---")
    _render_decklog_export(entries, total_cards)
