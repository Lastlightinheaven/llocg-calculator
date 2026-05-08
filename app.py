"""
Love Live OCG - Live Success Probability Calculator
Streamlit web app for calculating the probability of successfully performing
a Live given a player's deck, cards already used, members on stage, and Live requirements.
"""
import streamlit as st
import pandas as pd
import random
import base64
from pathlib import Path

from models import (
    Color, COLOR_LABELS_TH, COLOR_EMOJI,
    DeckComposition, WaitingRoom, LiveRequirement,
    StageMembers, GameState,
)
from probability import calculate_live_success_probability, calculate_score_plus_probability, compute_non_trigger_sensitivity
from simulator import simulate_live
from card_db import (
    get_live_cards, fetch_live_cards_from_web, save_snapshot,
    get_card_index, fetch_card_index_from_web, save_card_index, strip_rarity_suffix,
)
from deck_import import (
    DecklogError, compose_deck_from_entries,
    fetch_deck_from_decklog, parse_pasted_deck_list,
)


st.set_page_config(
    page_title="LLOCG Live Probability Calculator",
    page_icon="🎤",
    layout="wide",
)

st.markdown("""
<style>
/* ── Import fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@400;500;600;700;800&family=Noto+Sans:wght@400;500;600;700;800&display=swap');

/* ════════════════════════════
   COLOR TOKENS (Dark theme + Pink accent)
   ════════════════════════════ */
:root {
    --llocg-pink:      #e91e8c;
    --llocg-pink-dark: #c4177a;
    --llocg-pink-light:#4a1535;
    --llocg-pink-pale: #2d0a2e;
    --llocg-text:      #f0e6ff;
    --llocg-text-sub:  #c4a8d4;
    --llocg-card:      #2d1040;
    --llocg-border:    #6b2d6b;
    --llocg-shadow:    0 2px 12px rgba(233,30,140,0.2);
    --llocg-shadow-md: 0 4px 20px rgba(233,30,140,0.3);
}

/* ════════════════════════════
   BASE — ปล่อยให้ Streamlit dark theme ทำงาน
   เราแค่เพิ่ม pink accent ทับ
   ════════════════════════════ */
html, body {
    font-family: 'Noto Sans Thai', 'Noto Sans', sans-serif !important;
}

/* ── Headers ── */
h1 {
    font-weight: 800 !important;
    color: #fff !important;
    -webkit-text-fill-color: #fff !important;
    background: var(--llocg-pink) !important;
    padding: 0.55em 1.2em !important;
    border-radius: 0 0 16px 16px !important;
    margin-bottom: 1.2em !important;
    box-shadow: var(--llocg-shadow-md) !important;
}
h2 {
    font-weight: 700 !important;
    color: var(--llocg-pink) !important;
    -webkit-text-fill-color: var(--llocg-pink) !important;
    border-bottom: 2px solid var(--llocg-border) !important;
    padding-bottom: 0.3em !important;
}
h3 {
    font-weight: 700 !important;
    color: var(--llocg-pink) !important;
    -webkit-text-fill-color: var(--llocg-pink) !important;
}

/* ── Buttons ── */
div[data-testid="stButton"] > button {
    background: var(--llocg-pink) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    padding: 0.45em 1.4em !important;
    box-shadow: 0 2px 8px rgba(233,30,140,0.4) !important;
    transition: all 0.15s ease !important;
}
div[data-testid="stButton"] > button:hover {
    background: var(--llocg-pink-dark) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(233,30,140,0.55) !important;
}
[data-testid="stNumberInput"] button {
    background: var(--llocg-pink) !important;
    color: #fff !important;
    border: none !important;
}
[data-testid="stNumberInput"] button:hover {
    background: var(--llocg-pink-dark) !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: var(--llocg-card) !important;
    border: 1.5px solid var(--llocg-border) !important;
    border-top: 3px solid var(--llocg-pink) !important;
    border-radius: 12px !important;
    box-shadow: var(--llocg-shadow) !important;
    padding: 1rem 1.25rem !important;
}
[data-testid="stMetricLabel"] {
    color: var(--llocg-pink) !important;
    font-weight: 700 !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    border: 1.5px solid var(--llocg-border) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    display: flex !important;
    align-items: center !important;
}
[data-testid="stExpander"] summary::before {
    content: "▶";
    font-size: 0.7em;
    color: var(--llocg-pink);
    margin-right: 6px;
    flex-shrink: 0;
}
details[open] > summary::before { content: "▼"; }
/* ซ่อนเฉพาะ icon span (span ที่มี class ขึ้นต้นด้วย st-emotion-cache และไม่มีข้อความ) */
[data-testid="stExpander"] summary > span[data-testid="stExpanderToggleIcon"],
[data-testid="stExpander"] summary > div > svg,
[data-testid="stExpander"] summary svg {
    display: none !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [role="tab"] {
    font-weight: 700 !important;
    color: var(--llocg-pink) !important;
    border-radius: 8px 8px 0 0 !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    background: var(--llocg-pink) !important;
    color: #fff !important;
    -webkit-text-fill-color: #fff !important;
}

/* ── Input wrapper ── */
[data-testid="stNumberInput"] > div,
[data-testid="stTextInput"] > div,
[data-testid="stTextArea"] > div {
    border: 1.5px solid var(--llocg-border) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
[data-testid="stNumberInput"] > div:focus-within,
[data-testid="stTextInput"] > div:focus-within {
    border-color: var(--llocg-pink) !important;
    box-shadow: 0 0 0 3px rgba(233,30,140,0.2) !important;
}
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
}

/* ── Widget labels — คืนให้แสดงเสมอ ── */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label,
label[data-testid] {
    visibility: visible !important;
    width: auto !important;
    overflow: visible !important;
    height: auto !important;
    opacity: 1 !important;
}

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div {
    border: 1.5px solid var(--llocg-border) !important;
    border-radius: 12px !important;
    transition: border-color 0.15s !important;
}
[data-testid="stSelectbox"] > div > div:focus-within {
    border-color: var(--llocg-pink) !important;
}
[data-testid="stSelectbox"] svg { color: var(--llocg-pink) !important; }

/* ── Alert ── */
[data-testid="stAlert"] {
    border-left: 4px solid var(--llocg-pink) !important;
    border-radius: 10px !important;
}

/* ── Divider ── */
hr {
    border: none !important;
    height: 2px !important;
    background: linear-gradient(90deg, transparent, var(--llocg-pink), transparent) !important;
    opacity: 0.4 !important;
    margin: 1em 0 !important;
}

/* ── Caption ── */
[data-testid="stCaptionContainer"] {
    color: var(--llocg-text-sub) !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--llocg-pink-pale); border-radius: 10px; }
::-webkit-scrollbar-thumb { background: var(--llocg-pink); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: var(--llocg-pink-dark); }
</style>
""", unsafe_allow_html=True)


# ---------- Helpers ----------
HEART_COLORS = [Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW, Color.PURPLE, Color.PINK]
CUSTOM_LIVE_OPTION = "— กำหนดเอง —"


def color_label(color: Color) -> str:
    return f"{COLOR_EMOJI[color]} {COLOR_LABELS_TH[color]}"


def _prob_bar(probability: float) -> None:
    """แสดง progress bar ที่มีสีไล่จากแดง (0%) → เหลือง (50%) → เขียว (100%) พร้อมตัวเลขบนแถบ."""
    pct = max(0.0, min(1.0, probability))
    pct_display = pct * 100
    # Hue: 0° = red, 120° = green — linear interpolation
    hue = int(pct * 120)
    bar_color = f"hsl({hue}, 80%, 42%)"
    st.markdown(
        f"""
        <div style="
            position:relative;
            background:#e0e0e0;
            border-radius:8px;
            height:36px;
            width:100%;
            overflow:hidden;
            margin:6px 0 10px 0;
        ">
            <div style="
                width:{pct_display:.2f}%;
                height:100%;
                background:{bar_color};
                border-radius:8px;
                transition:width 0.3s;
            "></div>
            <span style="
                position:absolute;
                top:50%;
                left:50%;
                transform:translate(-50%,-50%);
                font-weight:800;
                font-size:1.05em;
                color:#fff;
                -webkit-text-stroke:2px #333;
                paint-order:stroke fill;
                white-space:nowrap;
            ">{pct_display:.2f}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_failure_breakdown(sim) -> None:
    """แสดงสาเหตุที่ Live ไม่สำเร็จจาก Monte Carlo trials"""
    from models import COLOR_LABELS_TH, COLOR_EMOJI, Color
    bd = sim.failure_breakdown
    if bd is None:
        return
    total_fails = sim.trials - sim.successes
    if total_fails <= 0:
        return

    with st.expander(f"🔍 สาเหตุที่ไม่สำเร็จ ({total_fails:,} trials)"):
        rows = []
        for color_val, count in sorted(bd.missing_specific_color.items(), key=lambda x: -x[1]):
            try:
                c = Color(color_val)
                label = f"{COLOR_EMOJI.get(c, '')} ขาด Heart สี{COLOR_LABELS_TH.get(c, color_val)}"
            except ValueError:
                label = f"ขาด {color_val}"
            rows.append({"สาเหตุ": label, "จำนวน trials": count, "% ของ fail": f"{count/total_fails*100:.1f}%"})

        if bd.missing_total_hearts > 0:
            rows.append({"สาเหตุ": "⚡ Heart รวมไม่พอ (Gray/Any)", "จำนวน trials": bd.missing_total_hearts, "% ของ fail": f"{bd.missing_total_hearts/total_fails*100:.1f}%"})
        if bd.multiple_causes > 0:
            rows.append({"สาเหตุ": "⚠️ ขาดหลายสีพร้อมกัน", "จำนวน trials": bd.multiple_causes, "% ของ fail": f"{bd.multiple_causes/total_fails*100:.1f}%"})

        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _card_img_src(image: str) -> str:
    """
    แปลง image field เป็น src ที่ใช้ได้ใน <img> และ st.image().
    - ถ้าเป็น URL (http/https) → คืนตรงๆ
    - ถ้าเป็น local path → encode เป็น data URI (base64)
    """
    if not image:
        return ""
    if image.startswith("http://") or image.startswith("https://"):
        return image
    p = Path(image)
    if not p.exists():
        return ""
    data = base64.b64encode(p.read_bytes()).decode()
    suffix = p.suffix.lower().lstrip(".")
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
    return f"data:{mime};base64,{data}"


def _build_known_fixed_counts() -> dict:
    """คำนวณ trigger counts ของการ์ดที่รู้แน่ชัดว่าออกจาก Deck แล้ว
    (Stage slots + Board Live slots + Live สำเร็จ)
    คืน dict พร้อม score_plus_drawn สำหรับ Score+ Live
    """
    idx = st.session_state.get("card_index", {})
    live_lut = {c.card_no: c for c in st.session_state.get("live_cards", [])}
    counts: dict = {c.value: 0 for c in Color.trigger_colors()}
    counts["all"] = 0
    counts["non"] = 0
    counts["score_plus_drawn"] = 0
    for slot_prefix, slot_range in [("stage_slot_", range(3)), ("live_slot_", range(3))]:
        for i in slot_range:
            cn = st.session_state.get(f"{slot_prefix}{i}", "")
            card = idx.get(cn) if cn else None
            if not card:
                continue
            tc = card.trigger_color
            if tc is None:
                counts["non"] += 1
                lc = live_lut.get(cn)
                if lc and lc.score_plus > 0:
                    counts["score_plus_drawn"] += 1
            elif tc == Color.ALL:
                counts["all"] += 1
            elif tc.value in counts:
                counts[tc.value] += 1
    n_done = st.session_state.get("wr_done_live_count", 0)
    for i in range(n_done):
        cn = st.session_state.get(f"wr_done_live_{i}", "")
        card = idx.get(cn) if cn else None
        if not card:
            continue
        tc = card.trigger_color
        if tc is None:
            counts["non"] += 1
            lc = live_lut.get(cn)
            if lc and lc.score_plus > 0:
                counts["score_plus_drawn"] += 1
        elif tc == Color.ALL:
            counts["all"] += 1
        elif tc.value in counts:
            counts[tc.value] += 1
    return counts


def _build_unknown_pool() -> list[str]:
    """สร้าง pool ของการ์ดที่ยังไม่รู้ว่าออกมาเป็นอะไร
    = deck เต็ม หัก fixed (Stage/Board/Done)
    ใช้สำหรับสุ่มมือ + WR_extra
    """
    deck_colors = {
        Color.RED:    st.session_state.get("deck_red", 0),
        Color.BLUE:   st.session_state.get("deck_blue", 0),
        Color.GREEN:  st.session_state.get("deck_green", 0),
        Color.YELLOW: st.session_state.get("deck_yellow", 0),
        Color.PURPLE: st.session_state.get("deck_purple", 0),
        Color.PINK:   st.session_state.get("deck_pink", 0),
    }
    deck_all = st.session_state.get("deck_all", 0)
    sp_total = st.session_state.get("deck_score_plus_count", _calc_deck_score_plus_count())
    non_plain = st.session_state.get("deck_non_plain", 0)

    fixed = _build_known_fixed_counts()
    pool: list[str] = []
    for color in Color.trigger_colors():
        cnt = max(0, deck_colors[color] - fixed[color.value])
        pool.extend([color.value] * cnt)
    pool.extend(["all"] * max(0, deck_all - fixed["all"]))
    fixed_sp = fixed["score_plus_drawn"]
    fixed_non_plain = fixed["non"] - fixed_sp
    pool.extend(["non_sp"] * max(0, sp_total - fixed_sp))
    pool.extend(["non"] * max(0, non_plain - fixed_non_plain))
    return pool


def _sample_from_deck(n_draw: int) -> dict:
    """สุ่ม n_draw ใบจาก unknown pool (หัก Stage/Board/Done แล้ว)"""
    pool = _build_unknown_pool()
    n_draw = min(n_draw, len(pool))
    drawn = random.sample(pool, n_draw)

    counts: dict = {c.value: 0 for c in Color.trigger_colors()}
    counts["all"] = 0
    counts["non"] = 0
    counts["score_plus_drawn"] = 0
    for card in drawn:
        if card == "non_sp":
            counts["non"] += 1
            counts["score_plus_drawn"] += 1
        else:
            counts[card] += 1
    return counts



def _merge_wr_counts(*count_dicts) -> dict:
    """รวม count dicts หลายชุดเป็นชุดเดียว."""
    result: dict = {c.value: 0 for c in [Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW, Color.PURPLE, Color.PINK]}
    result["all"] = 0
    result["non"] = 0
    result["score_plus_drawn"] = 0
    for d in count_dicts:
        for k in result:
            result[k] = result.get(k, 0) + d.get(k, 0)
    return result


def _apply_wr_counts_to_state(counts: dict) -> None:
    """เขียน counts dict ลง session_state wr_* keys.
    counts["non"] = plain + score_plus รวมกัน; เขียนลง wr_non_plain โดยหัก score_plus_drawn ออก
    """
    st.session_state["wr_red"]    = counts[Color.RED.value]
    st.session_state["wr_blue"]   = counts[Color.BLUE.value]
    st.session_state["wr_green"]  = counts[Color.GREEN.value]
    st.session_state["wr_yellow"] = counts[Color.YELLOW.value]
    st.session_state["wr_purple"] = counts[Color.PURPLE.value]
    st.session_state["wr_pink"]   = counts[Color.PINK.value]
    st.session_state["wr_all"]    = counts["all"]
    sp_drawn = counts.get("score_plus_drawn", 0)
    st.session_state["wr_non_plain"] = max(0, counts["non"] - sp_drawn)


def _empty_counts() -> dict:
    counts = {c.value: 0 for c in [Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW, Color.PURPLE, Color.PINK]}
    counts["all"] = 0
    counts["non"] = 0
    return counts


def _calc_deck_score_plus_count() -> int:
    """นับ Score+ Live card ทั้งหมดใน deck จาก imported_entries + live_cards DB."""
    entries = st.session_state.get("imported_entries") or []
    if not entries:
        return 0
    live_lut = {c.card_no: c for c in st.session_state.get("live_cards", [])}
    return sum(
        e.count for e in entries
        if (lc := live_lut.get(e.card_no)) and lc.score_plus > 0
    )


def _score_plus_used() -> int:
    """นับ Score+ Live card ที่ออกจาก deck ไปแล้ว (บน Board + Live สำเร็จ)."""
    live_lut = {c.card_no: c for c in st.session_state.get("live_cards", [])}
    used = 0
    # Live cards บน Game Board (live_slot_*)
    for i in range(3):
        cn = st.session_state.get(f"live_slot_{i}", "")
        lc = live_lut.get(cn) if cn else None
        if lc and lc.score_plus > 0:
            used += 1
    # Live cards ที่เล่นสำเร็จแล้ว (wr_done_live_*)
    n_done = st.session_state.get("wr_done_live_count", 0)
    for i in range(n_done):
        cn = st.session_state.get(f"wr_done_live_{i}", "")
        lc = live_lut.get(cn) if cn else None
        if lc and lc.score_plus > 0:
            used += 1
    return used


def _resample_all_callback() -> None:
    """Callback ปุ่มสุ่มเดียว: สุ่มการ์ดที่ยังไม่รู้ (มือ + WR_extra) แล้วรวมกับ fixed."""
    n_hand = st.session_state.get("wr_hand_n") or 0
    n_extra = st.session_state.get("wr_extra_n") or 0
    n_unknown = n_hand + n_extra
    sample = _sample_from_deck(n_unknown) if n_unknown > 0 else _empty_counts()
    st.session_state["_wr_unknown_sample"] = sample
    # Score+ ที่สุ่มได้ใน unknown → เขียนลง wr_sp_extra (clamp ไม่เกิน max)
    sp_deck_total = _calc_deck_score_plus_count()
    sp_auto = _score_plus_used()
    sp_from_sample = sample.get("score_plus_drawn", 0)
    st.session_state["wr_sp_extra"] = min(sp_from_sample, max(0, sp_deck_total - sp_auto))
    # บันทึก snapshot สำหรับ stable total
    fixed = _build_known_fixed_counts()
    merged = _merge_wr_counts(fixed, sample)
    _apply_wr_counts_to_state(merged)
    # snapshot total
    sp_total = merged.get("score_plus_drawn", 0)
    total_merged = sum(merged[k] for k in merged if k != "score_plus_drawn") + sp_total
    st.session_state["_wr_merged_total"] = total_merged
    st.session_state["_wr_merged_hand_n"] = n_hand
    st.session_state["_wr_merged_extra_n"] = n_extra
    stage_n = sum(1 for i in range(3) if st.session_state.get(f"stage_slot_{i}", ""))
    live_n = sum(1 for i in range(3) if st.session_state.get(f"live_slot_{i}", ""))
    done_n = st.session_state.get("wr_done_live_count", 0)
    st.session_state["_wr_merged_fixed_out"] = stage_n + live_n + done_n


def _random_waiting_room_callback() -> None:
    """on_click callback สำหรับ manual mode: สุ่ม Waiting Room ทั้งหมดจาก deck."""
    n_draw = st.session_state.get("wr_rand_n_manual") or 10
    counts = _sample_from_deck(n_draw)
    _apply_wr_counts_to_state(counts)
    st.session_state["wr_sp_manual"] = counts.get("score_plus_drawn", 0)


def _ensure_card_db_loaded() -> None:
    """Load card DBs into session_state on first access (snapshot fast path)."""
    if "live_cards" not in st.session_state:
        cards, source = get_live_cards(force_refresh=False)
        st.session_state.live_cards = cards
        st.session_state.live_cards_source = source
    if "card_index" not in st.session_state:
        idx, source = get_card_index(force_refresh=False)
        st.session_state.card_index = idx
        st.session_state.card_index_source = source


def _apply_deck_composition(dc: DeckComposition) -> None:
    """เขียน DeckComposition ลง session_state keys ให้ deck number_input re-render."""
    st.session_state.deck_red = dc.trigger_counts.get(Color.RED, 0)
    st.session_state.deck_blue = dc.trigger_counts.get(Color.BLUE, 0)
    st.session_state.deck_green = dc.trigger_counts.get(Color.GREEN, 0)
    st.session_state.deck_yellow = dc.trigger_counts.get(Color.YELLOW, 0)
    st.session_state.deck_purple = dc.trigger_counts.get(Color.PURPLE, 0)
    st.session_state.deck_pink = dc.trigger_counts.get(Color.PINK, 0)
    st.session_state.deck_all = dc.all_trigger
    st.session_state.deck_score_plus_count = dc.score_plus_count
    st.session_state.deck_non_plain = dc.non_trigger - dc.score_plus_count


def _store_imported_deck(source: str, entries, title: str = "") -> None:
    """Persist รายการการ์ดที่ import สำเร็จ เพื่อแสดงตารางในรอบ render ถัดไป."""
    st.session_state.imported_entries = list(entries)
    st.session_state.imported_source = source      # "decklog" | "paste"
    st.session_state.imported_title = title
    # Reset game board slots so stale card selections don't carry over to new deck
    for _i in range(5):
        st.session_state[f"stage_slot_{_i}"] = ""
    for _i in range(3):
        st.session_state[f"live_slot_{_i}"] = ""


def _trigger_label(color) -> str:
    """แสดง trigger color ของการ์ด — None = Non-Trigger, ALL = 🌈, สีอื่น = emoji+ชื่อ"""
    if color is None:
        return "⬛ Non"
    if color == Color.ALL:
        return f"{COLOR_EMOJI[Color.ALL]} All"
    return f"{COLOR_EMOJI.get(color, '?')} {COLOR_LABELS_TH.get(color, color.value)}"


def _render_deck_gallery_body() -> None:
    """แสดงรูปการ์ดใน deck ที่ import มา จัดเป็น grid แยก Member / Live (body-only, no header)."""
    entries = st.session_state.get("imported_entries") or []
    if not entries:
        return
    card_index = st.session_state.get("card_index", {})

    # group by card_type
    groups: dict = {"member": [], "live": [], "energy": []}
    unknown = []
    for e in entries:
        card = card_index.get(e.card_no) or card_index.get(strip_rarity_suffix(e.card_no))
        if card is None:
            unknown.append(e)
        elif card.card_type in groups:
            groups[card.card_type].append((card, e.count))

    src = st.session_state.get("imported_source", "")
    if src:
        st.caption({"decklog": "ที่มา: 🔗 Decklog",
                    "paste": "ที่มา: 📋 Paste"}.get(src, src))

    type_info = {
        "member": ("🎭 Member", 9),
        "live":   ("🎵 Live",   5),
        "energy": ("🔋 Energy", 9),
    }
    for t, (label, cols_per_row) in type_info.items():
        items = groups[t]
        if not items:
            continue
        total = sum(c for _, c in items)
        st.subheader(f"{label}  —  {total} ใบ ({len(items)} แบบ)")
        for i in range(0, len(items), cols_per_row):
            row = items[i : i + cols_per_row]
            cols = st.columns(cols_per_row)
            for j, (card, count) in enumerate(row):
                with cols[j]:
                    caption = f"×{count}"
                    if card.trigger_color is not None:
                        caption = f"{COLOR_EMOJI.get(card.trigger_color, '')} {caption}"
                    if card.image:
                        st.image(_card_img_src(card.image), caption=caption, use_container_width=True)
                    else:
                        st.caption(f"{card.card_no}\n{caption}")
                    st.caption(f"`{card.card_no}`")

    if unknown:
        st.subheader(f"⚠️ ไม่พบใน DB ({len(unknown)} แบบ)")
        st.caption("การ์ดเหล่านี้ไม่มีในฐานข้อมูล — กดปุ่ม Refresh DB ด้านล่างเพื่อลองดึงใหม่")
        for e in unknown:
            st.text(f"  {e.card_no}  ×{e.count}")


# ── Game board constants ──────────────────────────────────────────────────
_SLOT_BG = "#fce4ec"
_SLOT_BG_CENTER = "#f8bbd0"
_SLOT_BORDER = "#e91e63"
_SLOT_TEXT = "#c2185b"


def _card_slot_placeholder(label: str, bg: str = _SLOT_BG, height: int = 140) -> None:
    """Styled empty card slot placeholder matching the game's pink theme."""
    st.markdown(
        f'<div style="background:{bg};border:2px dashed {_SLOT_BORDER};border-radius:10px;'
        f'height:{height}px;display:flex;align-items:center;justify-content:center;'
        f'color:{_SLOT_TEXT};font-size:0.72em;text-align:center;padding:8px;line-height:1.5;">'
        f'{label}</div>',
        unsafe_allow_html=True,
    )




def _build_lives_from_slots() -> list:
    """Build LiveRequirement list from 3 live slot selections (skip empty)."""
    live_lut = {c.card_no: c for c in st.session_state.get("live_cards", [])}
    idx = st.session_state.get("card_index", {})
    lives = []
    for i in range(3):
        card_no = st.session_state.get(f"live_slot_{i}", "")
        if not card_no:
            continue
        lc = live_lut.get(card_no)
        dc = idx.get(card_no)
        name = (lc.name if lc else (dc.name if dc else card_no)) or card_no
        req = dict(lc.required_hearts) if lc else {}
        lives.append(LiveRequirement(name=name, required_hearts=req))
    return lives


def _apply_board_to_inputs() -> None:
    """กดปุ่มยืนยัน Game Board → apply stage + live values ลง number_input keys ทั้งหมด."""
    idx = st.session_state.get("card_index", {})
    live_lut = {c.card_no: c for c in st.session_state.get("live_cards", [])}

    # Stage: รวม blade + base_heart จาก 3 slots
    hearts: dict = {c: 0 for c in [Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW, Color.PURPLE, Color.PINK]}
    total_blade = 0
    for i in range(3):
        card_no = st.session_state.get(f"stage_slot_{i}", "")
        card = idx.get(card_no) if card_no else None
        if card:
            for c, n in card.base_heart.items():
                if c in hearts:
                    hearts[c] += n
            total_blade += card.blade
    st.session_state["ov_blade"] = total_blade
    st.session_state["ov_sb_red"] = hearts[Color.RED]
    st.session_state["ov_sb_blue"] = hearts[Color.BLUE]
    st.session_state["ov_sb_green"] = hearts[Color.GREEN]
    st.session_state["ov_sb_yellow"] = hearts[Color.YELLOW]
    st.session_state["ov_sb_purple"] = hearts[Color.PURPLE]
    st.session_state["ov_sb_pink"] = hearts[Color.PINK]

    # Live: collect slots ที่มีการ์ด (pack ตามลำดับ → form index 0,1,2)
    filled_slots = [
        st.session_state.get(f"live_slot_{i}", "")
        for i in range(3)
        if st.session_state.get(f"live_slot_{i}", "")
    ]
    for form_i, card_no in enumerate(filled_slots):
        lc = live_lut.get(card_no)
        dc = idx.get(card_no)
        name = (lc.name if lc else (dc.name if dc else card_no)) or card_no
        st.session_state[f"live_name_gb_{form_i}"] = name
        for color in [Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW, Color.PURPLE, Color.PINK, Color.GRAY]:
            st.session_state[f"live_gb_{form_i}_{color.value}"] = (
                lc.required_hearts.get(color, 0) if lc else 0
            )
    st.session_state["n_lives_gb"] = max(1, min(3, len(filled_slots)))


def _render_card_picker_grid(card_nos: list, slot_key: str, cols: int = 4, card_w: int = 260) -> None:
    """
    แสดง image grid ให้ user คลิกเลือกการ์ด — เขียน card_no ลง session_state[slot_key].
    รูปการ์ดกดได้โดยตรง: selected = border ชมพู + overlay ✓, unselected = กดเพื่อเลือก
    """
    idx = st.session_state.get("card_index", {})
    selected = st.session_state.get(slot_key, "")

    if selected:
        if st.button("✖ ล้างการเลือก", key=f"clear_{slot_key}"):
            st.session_state[slot_key] = ""
            st.rerun()

    # inject CSS ครั้งเดียวต่อ grid เพื่อทำ image button
    st.markdown("""
    <style>
    div[data-testid="stButton"] > button.card-pick-btn {
        position: absolute; inset: 0; width: 100%; height: 100%;
        opacity: 0; cursor: pointer; border: none; background: none;
    }
    </style>
    """, unsafe_allow_html=True)

    grid_cols = st.columns(cols)
    for j, card_no in enumerate(card_nos):
        card = idx.get(card_no) or idx.get(strip_rarity_suffix(card_no))
        if not card or not card.image:
            continue
        with grid_cols[j % cols]:
            is_selected = (card_no == selected)
            border = "3px solid #e91e8c" if is_selected else "2px solid transparent"
            overlay = (
                '<div style="position:absolute;inset:0;background:rgba(233,30,140,0.22);'
                'display:flex;align-items:center;justify-content:center;'
                'font-size:2em;color:#fff;border-radius:7px;">✓</div>'
                if is_selected else ""
            )
            name_tip = card.name or card_no
            st.markdown(
                f'<div style="position:relative;border:{border};border-radius:8px;'
                f'overflow:hidden;margin-bottom:6px;max-width:{card_w}px;margin-left:auto;margin-right:auto;" title="{name_tip}">'
                f'<img src="{_card_img_src(card.image)}" style="width:100%;display:block;">'
                f'{overlay}</div>',
                unsafe_allow_html=True,
            )
            btn_label = f"✓ {name_tip}" if is_selected else name_tip
            if st.button(btn_label, key=f"pick_{slot_key}_{card_no}",
                         use_container_width=True,
                         type="primary" if is_selected else "secondary"):
                st.session_state[slot_key] = "" if is_selected else card_no
                st.rerun()


def _render_game_board() -> None:
    """
    Render game board: 3 Live card slots (top) + 5 Stage positions (bottom).
    Matches the physical LLOCG game layout.
    Slot selections are stored directly via widget keys live_slot_{i} / stage_slot_{i}.
    """
    entries = st.session_state.get("imported_entries") or []
    idx = st.session_state.get("card_index", {})
    live_lut = {c.card_no: c for c in st.session_state.get("live_cards", [])}

    # Build deduplicated option lists preserving deck order
    # ใช้ card.card_no (จาก Assets) แทน e.card_no (จาก decklog) เพื่อให้ idx.get() ทุกที่ทำงานถูก
    seen_m, seen_l = set(), set()
    member_nos, live_nos = [], []
    for e in entries:
        card = idx.get(e.card_no) or idx.get(strip_rarity_suffix(e.card_no))
        if not card:
            continue
        key = card.card_no  # ใช้ card_no จาก Assets เสมอ
        if card.card_type == "member" and key not in seen_m:
            seen_m.add(key)
            member_nos.append(key)
        elif card.card_type == "live" and key not in seen_l:
            seen_l.add(key)
            live_nos.append(key)

    member_opts = [""] + member_nos
    live_opts = [""] + live_nos


    def _card_img_centered(url: str, width: int = 150) -> None:
        """แสดงรูปการ์ด centered ด้วย fixed width."""
        src = _card_img_src(url)
        st.markdown(
            f'<div style="display:flex;justify-content:center;margin-bottom:4px;">'
            f'<img src="{src}" style="width:{width}px;border-radius:6px;"></div>',
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        # ── Live Card Storage ─────────────────────────────────────────────
        st.markdown(
            '<p style="text-align:center;color:#c2185b;font-weight:700;'
            'font-size:1.05em;margin:4px 0 10px 0;">🎵 Live Card Storage</p>',
            unsafe_allow_html=True,
        )
        live_c = st.columns(3)
        for i in range(3):
            with live_c[i]:
                _v = st.session_state.get(f"live_slot_{i}", "")
                if _v and _v not in live_opts:
                    st.session_state[f"live_slot_{i}"] = ""

                sel = st.session_state.get(f"live_slot_{i}", "")
                card = idx.get(sel) if sel else None
                if card and card.image:
                    _card_img_centered(card.image, width=260)
                else:
                    _card_slot_placeholder("Live card storage\nライブカード置き場", _SLOT_BG, 155)

                lc = live_lut.get(sel)
                if lc and lc.required_hearts:
                    st.caption("  ".join(
                        f"{COLOR_EMOJI.get(c, '')}×{n}"
                        for c, n in lc.required_hearts.items()
                    ))
                elif lc is None and sel:
                    st.caption("⚠️ ไม่พบข้อมูล required hearts — กด Refresh DB")

                # ปุ่มเลือก slot นี้
                _active_live = st.session_state.get("active_live_picker")
                _btn_label = "▲ ปิด" if _active_live == i else ("✏️ เปลี่ยน" if sel else "🃏 เลือก")
                if st.button(_btn_label, key=f"open_live_picker_{i}", use_container_width=True):
                    st.session_state["active_live_picker"] = None if _active_live == i else i
                    st.rerun()

        # ── Live Card Picker (แสดงใต้ row ทั้งหมด เมื่อ slot ใด slot หนึ่ง active) ──
        _active_live = st.session_state.get("active_live_picker")
        if _active_live is not None and live_nos:
            st.markdown(
                f'<p style="color:#c2185b;font-weight:600;margin:8px 0 4px 0;">'
                f'🃏 เลือก Live card สำหรับ Slot {_active_live + 1}</p>',
                unsafe_allow_html=True,
            )
            _render_card_picker_grid(live_nos, f"live_slot_{_active_live}", cols=3, card_w=260)

        st.markdown(
            '<hr style="border:none;border-top:2px solid #f8bbd0;margin:12px 0 10px 0;">',
            unsafe_allow_html=True,
        )

        # ── Stage ─────────────────────────────────────────────────────────
        st.markdown(
            '<p style="text-align:center;color:#c2185b;font-weight:700;'
            'font-size:1.05em;margin:0 0 6px 0;">🎭 Stage</p>',
            unsafe_allow_html=True,
        )
        pos_labels = ["Left Side ซ้าย", "Center กลาง", "Right Side ขวา"]
        stage_c = st.columns(3)
        for i in range(3):
            with stage_c[i]:
                st.markdown(
                    f'<p style="text-align:center;font-size:0.78em;color:#888;margin:0 0 4px 0;">'
                    f'{pos_labels[i]}</p>',
                    unsafe_allow_html=True,
                )

                _v = st.session_state.get(f"stage_slot_{i}", "")
                if _v and _v not in member_opts:
                    st.session_state[f"stage_slot_{i}"] = ""

                sel = st.session_state.get(f"stage_slot_{i}", "")
                card = idx.get(sel) if sel else None
                bg = _SLOT_BG_CENTER if i == 1 else _SLOT_BG

                if card and card.image:
                    _card_img_centered(card.image, width=150)
                else:
                    _card_slot_placeholder(pos_labels[i], bg, 155)

                now = idx.get(sel)
                if now:
                    bh = " ".join(
                        f"{COLOR_EMOJI.get(c, '')}×{n}"
                        for c, n in now.base_heart.items() if n > 0
                    )
                    bl = f"⚡×{now.blade}" if now.blade else ""
                    info = "  ".join(filter(None, [bl, bh]))
                    st.markdown(
                        f'<p style="text-align:center;font-size:0.82em;margin:2px 0 0 0;">{info or "—"}</p>',
                        unsafe_allow_html=True,
                    )

                _active_stage = st.session_state.get("active_stage_picker")
                _btn_label = "▲ ปิด" if _active_stage == i else ("✏️ เปลี่ยน" if sel else "🃏 เลือก")
                if st.button(_btn_label, key=f"open_stage_picker_{i}", use_container_width=True):
                    st.session_state["active_stage_picker"] = None if _active_stage == i else i
                    st.rerun()

        # ── Member Card Picker (แสดงใต้ row เมื่อ slot ใด slot หนึ่ง active) ──────
        _active_stage = st.session_state.get("active_stage_picker")
        if _active_stage is not None and member_nos:
            st.markdown(
                f'<p style="color:#c2185b;font-weight:600;margin:8px 0 4px 0;">'
                f'🃏 เลือก Member สำหรับ {pos_labels[_active_stage]}</p>',
                unsafe_allow_html=True,
            )
            _render_card_picker_grid(member_nos, f"stage_slot_{_active_stage}", cols=6, card_w=150)


def _apply_live_card_to_form(live_idx) -> None:
    """
    Callback เมื่อ user เลือก Live card จาก dropdown — เขียน required hearts
    ลง session_state เพื่อให้ number_input ข้างล่าง render ด้วยค่าใหม่.
    live_idx: int สำหรับ manual mode (keys live_*) หรือ str "gb_{i}" สำหรับ game board mode (keys live_gb_*)
    """
    if isinstance(live_idx, str) and live_idx.startswith("gb_"):
        # game board mode — keys: live_select_gb_{i}, live_name_gb_{i}, live_gb_{i}_{color}
        _i = live_idx[3:]
        sel = st.session_state.get(f"live_select_gb_{_i}")
        if not sel or sel == CUSTOM_LIVE_OPTION:
            return
        cards: list = st.session_state.get("live_cards", [])
        picked = next((c for c in cards if c.label() == sel), None)
        if picked is None:
            return
        st.session_state[f"live_name_gb_{_i}"] = picked.name
        for color in HEART_COLORS + [Color.GRAY]:
            st.session_state[f"live_gb_{_i}_{color.value}"] = picked.required_hearts.get(color, 0)
    else:
        # manual mode — keys: live_select_{live_idx}, live_name_{live_idx}, live_{live_idx}_{color}
        sel = st.session_state.get(f"live_select_{live_idx}")
        if not sel or sel == CUSTOM_LIVE_OPTION:
            return
        cards = st.session_state.get("live_cards", [])
        picked = next((c for c in cards if c.label() == sel), None)
        if picked is None:
            return
        st.session_state[f"live_name_{live_idx}"] = picked.name
        for color in HEART_COLORS + [Color.GRAY]:
            st.session_state[f"live_{live_idx}_{color.value}"] = picked.required_hearts.get(color, 0)


# Load Live-card DB (snapshot) เข้า session_state ครั้งเดียวตอน start
_ensure_card_db_loaded()

# Initialize game board slot keys (once per session)
for _slot_i in range(5):
    if f"stage_slot_{_slot_i}" not in st.session_state:
        st.session_state[f"stage_slot_{_slot_i}"] = ""
for _slot_i in range(3):
    if f"live_slot_{_slot_i}" not in st.session_state:
        st.session_state[f"live_slot_{_slot_i}"] = ""


# ---------- Header ----------
st.title("🎤 LLOCG Live Probability Calculator")
st.caption(
    "เครื่องมือคำนวณโอกาสเล่น Live สำเร็จ สำหรับเกม Love Live! Official Card Game · "
    "พัฒนาโดยใช้ Hypergeometric Distribution + Monte Carlo Simulation"
)

with st.expander("ℹ️ วิธีใช้งาน", expanded=False):
    st.markdown("""
### 🚀 เริ่มต้นใช้งาน

มี 2 วิธีในการตั้งค่า Deck:

---

#### วิธีที่ 1 — Import จาก Decklog (แนะนำ)
1. ไปที่แถบ **Sidebar ซ้าย** → กด **📥 Import Deck จาก Decklog**
2. ใส่ Deck code จาก [decklog-en.bushiroad.com](https://decklog-en.bushiroad.com/) แล้วกด **Import** (หรือ Paste รายการการ์ดโดยตรง)
3. ระบบจะดึงข้อมูลการ์ดและเติมค่า Deck อัตโนมัติ

---

#### วิธีที่ 2 — กรอกเอง (Manual Mode)
กรอกจำนวนการ์ดแต่ละประเภทใน Sidebar:
- **Trigger สี** (Red / Blue / Green / Yellow / Purple / Pink) — Member ที่มี Trigger สีนั้น
- **All Trigger** — การ์ดที่เมื่อเปิดใน Yell ใช้แทนหัวใจสีไหนก็ได้
- **Non-Trigger** — การ์ดที่ไม่มี Trigger (Live card และ Member ที่ไม่มี Blade Heart)
- รวมทั้งหมดต้อง = **60 ใบ**

---

### 🎮 ตั้งค่าสถานการณ์

#### 1. Game Board
วาง Member และ Live card ลงบอร์ดจำลองเหมือนโต๊ะจริง:
- **Live Card Storage** (3 ช่อง) — Live ที่จะเล่นเทิร์นนี้
- **Stage** (3 ช่อง) — Member ที่อยู่บนเวที
- กด **✅ ยืนยัน Game Board** เพื่อให้ระบบคำนวณ Blade, Basic Hearts และ Required Hearts อัตโนมัติ

#### 2. Waiting Room
การ์ดทั้งหมดที่ออกจาก Deck ไปแล้ว แบ่งเป็น 4 แหล่ง:
- **Stage** — Member ที่ถูกเรียกออกมา (ดึงจาก Game Board อัตโนมัติ)
- **Live สำเร็จ** — Live ที่เล่นไปแล้วในเทิร์นก่อน
- **มือ** — การ์ดที่อยู่ในมือตอนนี้ (สุ่มตามสัดส่วน Deck ได้)
- **Waiting Room จาก Turn ก่อน** — การ์ดที่อยู่ใน Waiting Room อยู่แล้ว สามารถระบุจำนวนการ์ดที่ออกแล้วให้ระบบสุ่มการ์ดที่ออกตามสัดส่วนของ Trigger ใน Deck ได้
- กด **✅ อัปเดต Waiting Room** เพื่อรวมทุกแหล่ง

#### 3. Stage Members & Blade
- ระบบดึงค่าจาก Game Board อัตโนมัติ หรือกรอกเองใน Manual Mode
- **Basic Hearts** = หัวใจที่ได้แน่จาก Member บนเวที (ไม่ต้องลุ้น Yell) ทั้งนี้หาก Member มีText ที่สามารถเพิ่มหัวใจ ต้องดำเนินการเพิ่มเองแบบ Manual
- **Blade รวม** = จำนวนการ์ดที่จะจั่วตอน Yell ทั้งนี้หาก Member มี Text ที่สามารถเพิ่ม Blade ต้องดำเนินการเพิ่มเองแบบ Manual

#### 4. Live Card(s) ที่จะเล่น
- เลือก Live สูงสุด **3 ใบ** ต่อเทิร์น — Required Hearts จะรวมกันทั้งหมด
- เลือกจากรายการที่ Import ไว้ หรือกรอก Required Hearts เองได้ ทั้งนี้หาก Live บางใบมี Text ที่เพิ่มหัวใจหรือ Blade ต้องดำเนินการเพิ่มเองแบบ Manual

---

### 📊 ผลการคำนวณ

กด **🎲 คำนวณความน่าจะเป็น** จะแสดง:
- **Exact Hypergeometric** — ค่าแม่นยำ 100% (คำนวณจาก Combination ทั้งหมด)
- **Monte Carlo Simulation** — จำลอง N ครั้ง ใช้ cross-check และรองรับกรณี Reshuffle
- **⭐ Score+** — โอกาสที่ Yell จะเจอ Live card ที่มี Score+ bonus
- **📉 ผลกระทบของ Non-Trigger** — กราฟแสดงว่าถ้า Non-Trigger เหลือใน Deck มากหรือน้อย โอกาสสำเร็จเปลี่ยนอย่างไร

---

### 📖 คำศัพท์สำคัญ

| คำ | ความหมาย |
|---|---|
| **Blade** | จำนวนการ์ดที่จั่วตอน Yell (= ผลรวม Blade ของ Member บนเวที) |
| **Basic Heart** | หัวใจที่ได้แน่จาก Member บนเวที ไม่ต้องรอ Yell |
| **Trigger** | หัวใจที่ได้เมื่อเปิดการ์ดนั้นตอน Yell |
| **All Trigger** | Trigger ที่ใช้แทนหัวใจสีไหนก็ได้ |
| **Non-Trigger** | การ์ดที่เปิดใน Yell แล้วไม่ได้หัวใจ |
| **Gray (requirement)** | ช่องที่หัวใจสีไหนก็เติมได้ |
| **Waiting Room** | การ์ดทั้งหมดที่ออกจาก Deck ไปแล้ว |
    """)

st.divider()

# ==========================================================================
# SIDEBAR: Deck composition
# ==========================================================================
with st.sidebar:
    st.header("🃏 Deck Composition")
    st.caption("Deck ของคุณ (รวม 60 ใบ)")

    # Defaults = 0 ทุกช่อง ให้ user กรอกเอง
    if "deck_red" not in st.session_state:
        st.session_state.deck_red = 0
        st.session_state.deck_blue = 0
        st.session_state.deck_green = 0
        st.session_state.deck_yellow = 0
        st.session_state.deck_purple = 0
        st.session_state.deck_pink = 0
        st.session_state.deck_all = 0
        st.session_state.deck_non_plain = 0

    # ---- Deck import (decklog / paste) ----
    _idx_size = len(st.session_state.get("card_index", {}))
    _idx_src = st.session_state.get("card_index_source", "empty")
    with st.expander("📥 Import Deck จาก Decklog", expanded=False):
        st.caption(
            f"Card DB: **{_idx_size}** ใบ "
            f"({ {'web':'🌐 live','snapshot':'💾 snapshot','empty':'❌ ว่าง'}.get(_idx_src, _idx_src) })"
        )

        tab_code, tab_paste = st.tabs(["🔗 Deck code", "📋 Paste"])

        with tab_code:
            st.caption("ใส่ deck code จาก https://decklog-en.bushiroad.com/ (เช่น 'ABC12')")
            code = st.text_input("Deck code", key="decklog_code",
                                 placeholder="เช่น ABC12", label_visibility="collapsed")
            if st.button("🔽 ดึงจาก Decklog", use_container_width=True, type="primary",
                         key="btn_import_decklog"):
                if not code.strip():
                    st.warning("กรุณาใส่ deck code")
                elif not st.session_state.get("card_index"):
                    st.error("Card DB ว่าง — กด Refresh DB ก่อน")
                else:
                    with st.spinner("กำลังเรียก decklog API..."):
                        try:
                            deck = fetch_deck_from_decklog(code.strip())
                            dc, warnings = compose_deck_from_entries(
                                deck.entries, st.session_state.card_index,
                                live_cards=st.session_state.get("live_cards", []),
                            )
                            _apply_deck_composition(dc)
                            _store_imported_deck("decklog", deck.entries, deck.title)
                            title_suffix = f" · “{deck.title}”" if deck.title else ""
                            st.success(
                                f"Import สำเร็จ: {sum(e.count for e in deck.entries)} ใบ "
                                f"({len(deck.entries)} แบบ){title_suffix}"
                            )
                            for w in warnings:
                                st.warning(w)
                        except DecklogError as e:
                            st.error(f"{e}")
                            st.caption("ลองใช้แท็บ **Paste** เพื่อใส่ list เอง")

        with tab_paste:
            st.caption(
                "Paste รายการการ์ด บรรทัดละ 1 การ์ด รองรับ format:\n"
                "`3 LL-bp1-001-R+` · `LL-bp1-001-R+ x3` · `LL-bp1-001-R+, 3` · `LL-bp1-001-R+`"
            )
            pasted = st.text_area(
                "Card list", key="paste_decklist", height=180,
                placeholder="3 LL-bp1-001-R+\n4 LL-bp1-002-R\n...",
                label_visibility="collapsed",
            )
            if st.button("✅ Parse & Apply", use_container_width=True,
                         key="btn_parse_paste"):
                entries = parse_pasted_deck_list(pasted or "")
                if not entries:
                    st.warning("Parse ไม่เจอ card_no ที่ valid")
                elif not st.session_state.get("card_index"):
                    st.error("Card DB ว่าง — กด Refresh DB ก่อน")
                else:
                    dc, warnings = compose_deck_from_entries(
                        entries, st.session_state.card_index,
                        live_cards=st.session_state.get("live_cards", []),
                    )
                    _apply_deck_composition(dc)
                    _store_imported_deck("paste", entries, "")
                    st.success(
                        f"Apply สำเร็จ: {sum(e.count for e in entries)} ใบ "
                        f"({len(entries)} แบบ)"
                    )
                    for w in warnings:
                        st.warning(w)

    # ---- Imported deck detail ----
    _imported = st.session_state.get("imported_entries") or []
    if _imported:
        _src = st.session_state.get("imported_source", "")
        _title = st.session_state.get("imported_title", "")
        _card_index = st.session_state.get("card_index", {})
        _total = sum(e.count for e in _imported)
        _src_emoji = {"decklog": "🔗", "paste": "📋"}.get(_src, "📥")
        header = f"{_src_emoji} การ์ดที่ import ({_total} ใบ · {len(_imported)} แบบ)"
        if _title:
            header += f" — {_title}"
        with st.expander(header, expanded=False):
            rows = []
            for e in _imported:
                card = _card_index.get(e.card_no) or _card_index.get(strip_rarity_suffix(e.card_no))
                if card is None:
                    rows.append({
                        "card_no": e.card_no,
                        "ชื่อ": "⚠️ ไม่พบใน DB",
                        "ประเภท": "-",
                        "Trigger": "-",
                        "จำนวน": e.count,
                    })
                else:
                    rows.append({
                        "card_no": card.card_no,
                        "ชื่อ": card.name or "-",
                        "ประเภท": {"member": "M", "live": "L", "energy": "E"}.get(
                            card.card_type, card.card_type
                        ),
                        "Trigger": _trigger_label(card.trigger_color),
                        "จำนวน": e.count,
                    })
            # sort: unknown first (warn), then type M→L→E, then by card_no
            _type_order = {"M": 0, "L": 1, "E": 2, "-": -1}
            rows.sort(key=lambda r: (_type_order.get(r["ประเภท"], 99), r["card_no"]))
            st.dataframe(
                pd.DataFrame(rows),
                hide_index=True,
                use_container_width=True,
            )
            _show_gallery = st.session_state.get("show_deck_gallery", False)
            _btn_gallery_label = "🙈 ซ่อนรูปการ์ด" if _show_gallery else "🖼️ ดูรูปการ์ด"
            if st.button(_btn_gallery_label, key="btn_show_gallery", use_container_width=True):
                st.session_state.show_deck_gallery = not _show_gallery
            if st.button("🗑️ ล้างรายการ import", key="btn_clear_imported",
                         use_container_width=True):
                st.session_state.imported_entries = []
                st.session_state.imported_source = ""
                st.session_state.imported_title = ""
                st.session_state.show_deck_gallery = False
                for _ci in range(5):
                    st.session_state[f"stage_slot_{_ci}"] = ""
                for _ci in range(3):
                    st.session_state[f"live_slot_{_ci}"] = ""
                st.rerun()

    st.subheader("Trigger Hearts by Color")
    deck_red = st.number_input(color_label(Color.RED), min_value=0, max_value=60, key="deck_red")
    deck_blue = st.number_input(color_label(Color.BLUE), min_value=0, max_value=60, key="deck_blue")
    deck_green = st.number_input(color_label(Color.GREEN), min_value=0, max_value=60, key="deck_green")
    deck_yellow = st.number_input(color_label(Color.YELLOW), min_value=0, max_value=60, key="deck_yellow")
    deck_purple = st.number_input(color_label(Color.PURPLE), min_value=0, max_value=60, key="deck_purple")
    deck_pink = st.number_input(color_label(Color.PINK), min_value=0, max_value=60, key="deck_pink")

    st.subheader("Special")
    deck_all = st.number_input(f"{COLOR_EMOJI[Color.ALL]} All Trigger (wildcard)",
                               min_value=0, max_value=60, key="deck_all")
    _auto_sp = _calc_deck_score_plus_count()
    _deck_non_plain_max = 60 - deck_all  # ป้องกัน max เป็นลบ
    deck_non_plain = st.number_input(
        "⬛ Non-Trigger (ธรรมดา)",
        min_value=0, max_value=_deck_non_plain_max, key="deck_non_plain",
        help="Member/Live card ที่ไม่มี Trigger heart (ไม่นับ Score+ Live)",
    )
    if _auto_sp > 0:
        deck_sp = _auto_sp
        st.number_input(
            "⭐ Score+ Live ใน Deck",
            min_value=deck_sp, max_value=deck_sp, value=deck_sp,
            key="deck_score_plus_manual",
            help="คำนวณอัตโนมัติจาก import — แก้ไขได้ที่ Deck Import",
            disabled=True,
        )
    else:
        deck_sp = st.number_input(
            "⭐ Score+ Live ใน Deck",
            min_value=0, max_value=12, key="deck_score_plus_manual",
            help="จำนวน Live card ใน Deck ที่มี Score+ effect (เมื่อ Yell เจอการ์ดนี้จะได้คะแนน bonus)",
        )
    deck_non = deck_non_plain + deck_sp  # total non-trigger = plain + Score+

    deck = DeckComposition(
        trigger_counts={
            Color.RED: deck_red, Color.BLUE: deck_blue, Color.GREEN: deck_green,
            Color.YELLOW: deck_yellow, Color.PURPLE: deck_purple, Color.PINK: deck_pink,
        },
        all_trigger=deck_all,
        non_trigger=deck_non,
        score_plus_count=deck_sp,
    )

    total = deck.total()
    if total == 60:
        st.success(f"✅ Deck total = {total}")
    else:
        st.error(f"⚠️ Deck total = {total} (ต้องเท่ากับ 60)")

    st.divider()
    st.subheader("📖 Live Card Database")
    _n_cards = len(st.session_state.get("live_cards", []))
    _src = st.session_state.get("live_cards_source", "empty")
    _src_label = {"web": "🌐 live", "snapshot": "💾 snapshot", "empty": "❌ ว่าง"}.get(_src, _src)
    st.caption(f"โหลด **{_n_cards}** ใบ · ที่มา: {_src_label}")
    if st.button("🔄 Refresh from DB", use_container_width=True,
                 help="ดึง Live + card index ล่าสุดจาก llocg-th.vercel.app (fallback → snapshot ถ้าพัง)"):
        with st.spinner("กำลังดึงข้อมูลจากเว็บ..."):
            try:
                fresh = fetch_live_cards_from_web()
                save_snapshot(fresh)
                st.session_state.live_cards = fresh
                st.session_state.live_cards_source = "web"
                idx_cards = fetch_card_index_from_web()
                save_card_index(idx_cards)
                st.session_state.card_index = {c.card_no: c for c in idx_cards}
                st.session_state.card_index_source = "web"
                st.success(
                    f"อัปเดตเรียบร้อย: Live {len(fresh)} ใบ · index {len(idx_cards)} ใบ"
                )
            except Exception as e:  # noqa: BLE001
                st.error(f"ดึงไม่สำเร็จ: {e}")
                st.caption("ใช้ snapshot เดิมต่อไป")
    st.markdown(
        "[🔗 เปิดเว็บต้นทาง →](https://llocg-th.vercel.app/cards)",
        unsafe_allow_html=False,
    )


# ==========================================================================
# DECK GALLERY (แสดงหลัง sidebar — widgets deck ถูก register ไปแล้วจึงไม่สูญหาย)
# ==========================================================================
if st.session_state.get("show_deck_gallery") and (st.session_state.get("imported_entries") or []):
    _g_entries = st.session_state.imported_entries
    _g_total = sum(e.count for e in _g_entries)
    _g_title = st.session_state.get("imported_title", "")
    _g_header = f"🖼️ รูปการ์ดใน Deck ({_g_total} ใบ · {len(_g_entries)} แบบ)"
    if _g_title:
        _g_header += f" — {_g_title}"
    st.subheader(_g_header)
    _render_deck_gallery_body()
    st.divider()

# ==========================================================================
# MAIN: Game state  (game board mode when deck imported, manual mode otherwise)
# ==========================================================================
_has_deck = bool(st.session_state.get("imported_entries"))

if _has_deck:
    # ── Game Board ─────────────────────────────────────────────────────────
    st.header("🎮 Game Board")
    _render_game_board()
    _lives_from_board = _build_lives_from_slots()

    if st.button("✅ ยืนยัน Game Board → อัปเดต Stage & Live", type="primary", use_container_width=True):
        _apply_board_to_inputs()
        st.session_state["active_live_picker"] = None
        st.session_state["active_stage_picker"] = None
        st.rerun()

    st.divider()

    # ── Stage & Blade Manual Input ─────────────────────────────────────────
    st.header("🎭 Stage Members")
    st.caption("จำนวน Blade และ Basic Hearts — ค่าเริ่มต้นมาจากการ์ดที่เลือกใน Game Board ปรับได้โดยตรง")
    _ov_cols = st.columns(4)
    with _ov_cols[0]:
        blade_count = st.number_input(
            "⚡ Blade รวม (จำนวนจั่ว Yell)",
            min_value=0, max_value=60, key="ov_blade",
        )
        st.markdown("**Basic Hearts**")
        sb_red = st.number_input(color_label(Color.RED), min_value=0, max_value=30, key="ov_sb_red")
        sb_blue = st.number_input(color_label(Color.BLUE), min_value=0, max_value=30, key="ov_sb_blue")
    with _ov_cols[1]:
        sb_green = st.number_input(color_label(Color.GREEN), min_value=0, max_value=30, key="ov_sb_green")
        sb_yellow = st.number_input(color_label(Color.YELLOW), min_value=0, max_value=30, key="ov_sb_yellow")
    with _ov_cols[2]:
        sb_purple = st.number_input(color_label(Color.PURPLE), min_value=0, max_value=30, key="ov_sb_purple")
        sb_pink = st.number_input(color_label(Color.PINK), min_value=0, max_value=30, key="ov_sb_pink")
    stage = StageMembers(
        basic_hearts={
            Color.RED: sb_red, Color.BLUE: sb_blue, Color.GREEN: sb_green,
            Color.YELLOW: sb_yellow, Color.PURPLE: sb_purple, Color.PINK: sb_pink,
        },
        blade_count=blade_count,
    )
    st.info(
        f"🎭 Basic Hearts รวม: **{stage.total_basic_hearts()}**  |  ⚡ Yell draws: **{blade_count}**"
    )

    st.divider()

    # ── Live Cards (game board mode — always editable) ─────────────────────
    st.header("🎵 Live Card(s) ที่จะเล่น")
    st.caption("กำหนด required hearts ของ Live แต่ละใบ (สูงสุด 3 Live ต่อเทิร์น) — เลือกจาก Game Board หรือปรับ Manual ได้")
    if "n_lives_gb" not in st.session_state:
        st.session_state.n_lives_gb = max(1, len(_lives_from_board))
    col_nl2, _ = st.columns([1, 3])
    with col_nl2:
        n_lives_ov = st.selectbox("จำนวน Live ที่จะเล่น", options=[1, 2, 3], key="n_lives_gb")
    _card_options_gb = [CUSTOM_LIVE_OPTION] + [c.label() for c in st.session_state.get("live_cards", [])]
    lives = []
    live_cols_ov = st.columns(n_lives_ov)
    for i in range(n_lives_ov):
        _preset = _lives_from_board[i] if i < len(_lives_from_board) else None
        with live_cols_ov[i]:
            st.subheader(f"Live #{i+1}")
            st.selectbox(
                "เลือกจาก DB (หรือกำหนดเอง)",
                options=_card_options_gb,
                index=0,
                key=f"live_select_gb_{i}",
                on_change=_apply_live_card_to_form,
                args=(f"gb_{i}",),
                help="เลือก Live จากรายการเพื่อเติม required hearts อัตโนมัติ",
            )
            _sel_gb = st.session_state.get(f"live_select_gb_{i}", "")
            if _sel_gb and _sel_gb != CUSTOM_LIVE_OPTION:
                _lc_gb = next((c for c in st.session_state.get("live_cards", []) if c.label() == _sel_gb), None)
                if _lc_gb and _lc_gb.image:
                    st.image(_card_img_src(_lc_gb.image), use_container_width=True)
            name_key_gb = f"live_name_gb_{i}"
            if name_key_gb not in st.session_state:
                st.session_state[name_key_gb] = _preset.name if _preset else f"Live {i+1}"
            for color in HEART_COLORS + [Color.GRAY]:
                k = f"live_gb_{i}_{color.value}"
                if k not in st.session_state:
                    st.session_state[k] = _preset.required_hearts.get(color, 0) if _preset else 0
            name_ov = st.text_input("ชื่อ Live", key=name_key_gb)
            req_ov = {}
            for color in HEART_COLORS + [Color.GRAY]:
                n_ov = st.number_input(
                    color_label(color), min_value=0, max_value=20,
                    key=f"live_gb_{i}_{color.value}",
                )
                if n_ov > 0:
                    req_ov[color] = n_ov
            lives.append(LiveRequirement(name=name_ov, required_hearts=req_ov))

    st.divider()

    # ── Waiting Room (แบบ 3 แหล่ง) ───────────────────────────────────────────
    st.header("🗑️ Waiting Room")
    st.caption("การ์ดที่ออกจาก Deck ไปแล้ว — ระบุจาก 3 แหล่งแล้วระบบรวมให้อัตโนมัติ")

    _idx_wr = st.session_state.get("card_index", {})
    def _idx_lookup(card_no: str):
        return _idx_wr.get(card_no) or _idx_wr.get(strip_rarity_suffix(card_no))

    _live_nos_wr = [
        e.card_no for e in (st.session_state.get("imported_entries") or [])
        if (c := _idx_lookup(e.card_no)) and c.card_type == "live"
    ]

    # ── แหล่ง 1: Stage & Live บน Board (อ่านจาก Game Board อัตโนมัติ) ─────────
    _stage_count = sum(1 for i in range(3) if st.session_state.get(f"stage_slot_{i}", ""))
    _board_live_count = sum(1 for i in range(3) if st.session_state.get(f"live_slot_{i}", ""))
    _fixed_source1 = _stage_count + _board_live_count
    with st.expander(
        f"🎭 Stage & Live บน Board — {_fixed_source1} ใบ "
        f"(Stage {_stage_count} + Live {_board_live_count})",
        expanded=False,
    ):
        _sc_lines = []
        for i in range(3):
            _cn = st.session_state.get(f"stage_slot_{i}", "")
            if not _cn:
                continue
            _cd = _idx_wr.get(_cn)
            _name = _cd.name if _cd else _cn
            _tc = _cd.trigger_color if _cd else None
            _sc_lines.append(f"- 🎭 {_name} → {_trigger_label(_tc)}")
        for i in range(3):
            _cn = st.session_state.get(f"live_slot_{i}", "")
            if not _cn:
                continue
            _cd = _idx_wr.get(_cn)
            _name = _cd.name if _cd else _cn
            _sc_lines.append(f"- 🎵 Live: {_name}")
        if _sc_lines:
            st.markdown("\n".join(_sc_lines))
        else:
            st.caption("ยังไม่ได้เลือก Member / Live ใน Game Board")

    # ── แหล่ง 2: Live สำเร็จ ────────────────────────────────────────────────
    with st.expander("🎵 Live สำเร็จ (เลือกการ์ดที่เล่นไปแล้ว)", expanded=True):
        if "wr_done_live_count" not in st.session_state:
            st.session_state["wr_done_live_count"] = 0
        _dl_col1, _ = st.columns([1, 3])
        with _dl_col1:
            _dl_n = st.number_input(
                "จำนวน Live สำเร็จ", min_value=0, max_value=2, step=1,
                key="wr_done_live_count",
            )
        _live_opts_wr = [""] + _live_nos_wr
        for _di in range(_dl_n):
            _dl_key = f"wr_done_live_{_di}"
            if _dl_key not in st.session_state:
                st.session_state[_dl_key] = ""
            _dl_sel = st.session_state.get(_dl_key, "")
            _dl_card = _idx_wr.get(_dl_sel) if _dl_sel else None
            _dl_label = f"Live สำเร็จ #{_di + 1}"
            _dl_c1, _dl_c2 = st.columns([3, 1])
            with _dl_c1:
                st.selectbox(
                    _dl_label,
                    options=_live_opts_wr,
                    format_func=lambda cn: (_idx_wr[cn].name if cn and _idx_wr.get(cn) else ("— เลือกการ์ด —" if not cn else cn)),
                    key=_dl_key,
                )
                if _dl_card:
                    tc = _dl_card.trigger_color
                    st.caption(_trigger_label(tc))
            with _dl_c2:
                if _dl_card and _dl_card.image:
                    _dl_img_src = _card_img_src(_dl_card.image)
                    st.markdown(
                        f'<div style="margin-top:4px;">'
                        f'<img src="{_dl_img_src}" style="width:100%;border-radius:6px;"></div>',
                        unsafe_allow_html=True,
                    )

    # ── Step 1: คำนวณจำนวนการ์ดรวม ───────────────────────────────────────────
    _fixed_out = _fixed_source1 + st.session_state.get("wr_done_live_count", 0)
    _deck_total = deck.total()
    _remaining_for_unknown = max(0, _deck_total - _fixed_out)
    _current_hand_n = st.session_state.get("wr_hand_n", 0)
    _max_hand = _remaining_for_unknown
    _max_wr_extra = max(0, _remaining_for_unknown - _current_hand_n)
    _current_wr_extra_n = st.session_state.get("wr_extra_n", 0)
    _n_unknown = _current_hand_n + _current_wr_extra_n  # การ์ดที่ไม่รู้สี
    _total_out = _fixed_out + _n_unknown
    _remaining_in_deck_pre = max(0, _deck_total - _total_out)

    # reset sample cache ถ้าจำนวนเปลี่ยนหลังสุ่มครั้งล่าสุด
    if st.session_state.get("_wr_merged_total") is not None and (
        st.session_state.get("_wr_merged_hand_n") != _current_hand_n
        or st.session_state.get("_wr_merged_extra_n") != _current_wr_extra_n
        or st.session_state.get("_wr_merged_fixed_out") != _fixed_out
    ):
        st.session_state["_wr_merged_total"] = None
        st.session_state["_wr_unknown_sample"] = None

    # แสดง Step 1 summary
    _step1_parts = []
    if _fixed_source1 > 0:
        _step1_parts.append(f"Stage+Board **{_fixed_source1}** ใบ")
    _done_n_s1 = st.session_state.get("wr_done_live_count", 0)
    if _done_n_s1 > 0:
        _step1_parts.append(f"Live สำเร็จ **{_done_n_s1}** ใบ")
    if _current_hand_n > 0:
        _step1_parts.append(f"มือ **{_current_hand_n}** ใบ")
    if _current_wr_extra_n > 0:
        _step1_parts.append(f"WR turn ก่อน **{_current_wr_extra_n}** ใบ")
    _step1_str = " + ".join(_step1_parts) if _step1_parts else "ยังไม่มีข้อมูล"

    _ic1, _ic2, _ic3 = st.columns(3)
    with _ic1:
        st.metric("ออกจาก Deck", f"{_total_out} ใบ")
    with _ic2:
        st.metric("คงเหลือใน Deck", f"{_remaining_in_deck_pre} ใบ")
    with _ic3:
        st.metric("ยังไม่รู้สี (มือ+WR)", f"{_n_unknown} ใบ")
    if _step1_parts:
        st.caption(f"↳ {_step1_str}")

    # ── Input จำนวนมือและ WR turn ก่อน ──────────────────────────────────────
    _nc1, _nc2 = st.columns(2)
    with _nc1:
        st.number_input(
            "✋ จำนวนการ์ดในมือ", min_value=0, max_value=_max_hand, value=min(4, _max_hand),
            key="wr_hand_n",
            help="การ์ดในมือของคุณ (ยังอยู่ในมือ ไม่ได้ลง Waiting Room)",
        )
    with _nc2:
        st.number_input(
            "🗑️ การ์ดใน WR จาก Turn ก่อน", min_value=0, max_value=_max_wr_extra, value=0,
            key="wr_extra_n",
            help="การ์ดที่อยู่ใน Waiting Room จาก Turn ก่อนหน้า",
        )

    # ── Step 2: ปุ่มสุ่มเดียว ────────────────────────────────────────────────
    _has_unknown = (_current_hand_n + _current_wr_extra_n) > 0
    _has_sample = st.session_state.get("_wr_unknown_sample") is not None
    _btn_label = "🎲 สุ่มการ์ดที่ยังไม่รู้สีใหม่" if _has_sample else "🎲 สุ่มการ์ดที่ยังไม่รู้สี"
    if _has_unknown:
        st.button(
            _btn_label, key="btn_resample_all",
            on_click=_resample_all_callback, type="primary", use_container_width=False,
            help=f"สุ่มการแจกสีของการ์ด {_current_hand_n + _current_wr_extra_n} ใบที่ยังไม่รู้สีตามสัดส่วน Deck",
        )
    else:
        st.caption("ℹ️ ไม่มีการ์ดที่ยังไม่รู้สี (มือ+WR = 0)")

    # แสดงผลการสุ่มล่าสุด (Deck ที่เหลือ)
    _unknown_sample = st.session_state.get("_wr_unknown_sample")
    if _unknown_sample is not None:
        _fixed_counts = _build_known_fixed_counts()
        _rem_rows = []
        for _c in Color.trigger_colors():
            _rem = max(0, deck.count(_c) - _fixed_counts[_c.value] - _unknown_sample.get(_c.value, 0))
            if _rem > 0:
                _rem_rows.append({"ประเภท": color_label(_c), "เหลือใน Deck": _rem, "ออกไปแล้ว": deck.count(_c) - _rem})
        _rem_all = max(0, deck.all_trigger - _fixed_counts["all"] - _unknown_sample.get("all", 0))
        if _rem_all > 0 or deck.all_trigger > 0:
            _rem_rows.append({"ประเภท": f"{COLOR_EMOJI[Color.ALL]} All Trigger", "เหลือใน Deck": _rem_all, "ออกไปแล้ว": deck.all_trigger - _rem_all})
        _fixed_sp = _fixed_counts["score_plus_drawn"]
        _unk_sp = _unknown_sample.get("score_plus_drawn", 0)
        _unk_non_plain = _unknown_sample.get("non", 0) - _unk_sp
        _rem_sp = max(0, deck_sp - _fixed_sp - _unk_sp)
        _rem_non_plain = max(0, deck_non_plain - max(0, _fixed_counts["non"] - _fixed_sp) - _unk_non_plain)
        if deck_non_plain > 0:
            _rem_rows.append({"ประเภท": "⬛ Non-Trigger (ธรรมดา)", "เหลือใน Deck": _rem_non_plain, "ออกไปแล้ว": deck_non_plain - _rem_non_plain})
        if deck_sp > 0:
            _rem_rows.append({"ประเภท": "⭐ Score+ Live", "เหลือใน Deck": _rem_sp, "ออกไปแล้ว": deck_sp - _rem_sp})
        with st.expander("📊 Deck ที่เหลือ (จากการสุ่มล่าสุด)", expanded=True):
            if _rem_rows:
                st.dataframe(pd.DataFrame(_rem_rows), hide_index=True, use_container_width=True)

    st.divider()

    # ── Step 3: Input การ์ดที่ออกจาก Deck (แก้ไขได้) ─────────────────────────
    st.markdown("**📝 การ์ดที่ออกจาก Deck — ปรับแก้ได้ตามต้องการ**")
    st.caption("ค่าจากการสุ่มจะถูกเติมให้อัตโนมัติ แต่สามารถแก้ไขเองได้")

    # clamp WR session state values ให้ไม่เกิน deck count ปัจจุบัน
    for _wr_key, _wr_max in [
        ("wr_red", deck_red), ("wr_blue", deck_blue), ("wr_green", deck_green),
        ("wr_yellow", deck_yellow), ("wr_purple", deck_purple), ("wr_pink", deck_pink),
        ("wr_all", deck_all), ("wr_non_plain", deck_non_plain),
    ]:
        if st.session_state.get(_wr_key, 0) > _wr_max:
            st.session_state[_wr_key] = _wr_max

    _wrc = st.columns(4)
    with _wrc[0]:
        wr_red = st.number_input(color_label(Color.RED), min_value=0, max_value=deck_red, key="wr_red")
        wr_blue = st.number_input(color_label(Color.BLUE), min_value=0, max_value=deck_blue, key="wr_blue")
    with _wrc[1]:
        wr_green = st.number_input(color_label(Color.GREEN), min_value=0, max_value=deck_green, key="wr_green")
        wr_yellow = st.number_input(color_label(Color.YELLOW), min_value=0, max_value=deck_yellow, key="wr_yellow")
    with _wrc[2]:
        wr_purple = st.number_input(color_label(Color.PURPLE), min_value=0, max_value=deck_purple, key="wr_purple")
        wr_pink = st.number_input(color_label(Color.PINK), min_value=0, max_value=deck_pink, key="wr_pink")
    with _wrc[3]:
        wr_all = st.number_input(f"{COLOR_EMOJI[Color.ALL]} All Trigger",
                                 min_value=0, max_value=deck_all, key="wr_all")
        wr_non_plain = st.number_input(
            "⬛ Non-Trigger (ธรรมดา)",
            min_value=0, max_value=deck_non_plain, key="wr_non_plain",
            help="Non-Trigger ธรรมดาที่ออกไปแล้ว (ไม่นับ Score+ Live)",
        )

    # Score+ Live card ที่ออกจาก Deck แล้ว
    _sp_deck_total = _calc_deck_score_plus_count()
    _sp_auto = _score_plus_used()   # จาก live_slot + wr_done_live
    if _sp_deck_total > 0:
        _sp_max_extra = max(0, _sp_deck_total - _sp_auto)
        if "wr_sp_extra" not in st.session_state:
            st.session_state["wr_sp_extra"] = 0
        _spc1, _spc2 = st.columns([1, 2])
        with _spc1:
            wr_sp_extra = st.number_input(
                "⭐ Score+ Live ที่ออกไปทางอื่น",
                min_value=0, max_value=_sp_max_extra,
                key="wr_sp_extra",
                help="Score+ Live card ที่อยู่ในมือหรือ Waiting Room จาก turn ก่อน (นอกเหนือจาก Board + Live สำเร็จ)",
            )
        with _spc2:
            st.caption(
                f"จาก Board & Live สำเร็จ: **{_sp_auto}** ใบ  +  ทางอื่น: **{wr_sp_extra}** ใบ  "
                f"= ออกไปแล้ว **{_sp_auto + wr_sp_extra}** / {_sp_deck_total} ใบ  "
                f"→ เหลือใน Deck **{max(0, _sp_deck_total - _sp_auto - wr_sp_extra)}** ใบ"
            )
        wr_sp_count = _sp_auto + wr_sp_extra
    else:
        wr_sp_count = 0
    wr_non = wr_non_plain + wr_sp_count  # total non-trigger = plain + Score+

    waiting = WaitingRoom(
        trigger_counts={
            Color.RED: wr_red, Color.BLUE: wr_blue, Color.GREEN: wr_green,
            Color.YELLOW: wr_yellow, Color.PURPLE: wr_purple, Color.PINK: wr_pink,
        },
        all_trigger=wr_all,
        non_trigger=wr_non,
        score_plus_count=wr_sp_count,
    )
    wr_total = waiting.total()
    _hand_n = _current_hand_n
    _all_out = _total_out
    _stage_n = sum(1 for _si in range(5) if st.session_state.get(f"stage_slot_{_si}", ""))
    _live_slot_n = sum(1 for _li in range(3) if st.session_state.get(f"live_slot_{_li}", ""))
    _done_live_n = st.session_state.get("wr_done_live_count", 0)
    _cards_not_in_redeck = _hand_n + _stage_n + _live_slot_n + _done_live_n
    _redeck_size = max(0, _all_out - _cards_not_in_redeck)
    _remaining_in_deck = _remaining_in_deck_pre
    _non_plain_in_deck = deck_non_plain
    _sp_min_required = max(0, wr_non_plain - _non_plain_in_deck)
    if _all_out > total:
        st.error(f"⚠️ การ์ดที่ออกจาก Deck = **{_all_out}** ใบ เกินจำนวน Deck ({total} ใบ) — กรุณาตรวจสอบข้อมูล")
    elif _sp_min_required > 0 and wr_sp_count < _sp_min_required:
        st.warning(
            f"⚠️ Non-Trigger ธรรมดาที่ออกไป ({wr_non_plain} ใบ) เกินกว่าที่มีใน Deck ({_non_plain_in_deck} ใบ) — "
            f"Score+ Live ต้องออกไปแล้วอย่างน้อย **{_sp_min_required}** ใบ แต่กรอกไว้ {wr_sp_count} ใบ กรุณาตรวจสอบ"
        )
    elif _remaining_in_deck == 0 and _redeck_size > 0:
        _excl_parts = [f"มือ {_hand_n} ใบ"]
        if _stage_n:
            _excl_parts.append(f"Stage {_stage_n} ใบ")
        if _live_slot_n:
            _excl_parts.append(f"Live ที่จะเล่น {_live_slot_n} ใบ")
        if _done_live_n:
            _excl_parts.append(f"Live สำเร็จ {_done_live_n} ใบ")
        st.warning(
            f"⚠️ Deck หมดแล้ว — **Redeck**: {_redeck_size} ใบ "
            f"(ยกเว้น {', '.join(_excl_parts)} ที่ไม่ถูก shuffle กลับ) "
            f"จะถูก shuffle กลับเป็น Deck ใหม่"
        )

else:
    # ── Manual mode (no deck imported) ────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.header("🗑️ Waiting Room")
        st.caption("การ์ดที่ออกจาก Deck ไปแล้ว (Waiting Room / Stage / Live สำเร็จ)")

        # clamp WR session state values ให้ไม่เกิน deck count ปัจจุบัน
        for _wr_key, _wr_max in [
            ("wr_red", deck_red), ("wr_blue", deck_blue), ("wr_green", deck_green),
            ("wr_yellow", deck_yellow), ("wr_purple", deck_purple), ("wr_pink", deck_pink),
            ("wr_all", deck_all), ("wr_non_plain", deck_non_plain),
        ]:
            if st.session_state.get(_wr_key, 0) > _wr_max:
                st.session_state[_wr_key] = _wr_max

        wr_red = st.number_input(color_label(Color.RED), min_value=0, max_value=deck_red, key="wr_red", value=0)
        wr_blue = st.number_input(color_label(Color.BLUE), min_value=0, max_value=deck_blue, key="wr_blue", value=0)
        wr_green = st.number_input(color_label(Color.GREEN), min_value=0, max_value=deck_green, key="wr_green", value=0)
        wr_yellow = st.number_input(color_label(Color.YELLOW), min_value=0, max_value=deck_yellow, key="wr_yellow", value=0)
        wr_purple = st.number_input(color_label(Color.PURPLE), min_value=0, max_value=deck_purple, key="wr_purple", value=0)
        wr_pink = st.number_input(color_label(Color.PINK), min_value=0, max_value=deck_pink, key="wr_pink", value=0)
        wr_all = st.number_input(f"{COLOR_EMOJI[Color.ALL]} All Trigger",
                                 min_value=0, max_value=deck_all, key="wr_all", value=0)
        wr_non_plain = st.number_input(
            "⬛ Non-Trigger (ธรรมดา)",
            min_value=0, max_value=deck_non_plain, key="wr_non_plain", value=0,
            help="Non-Trigger ธรรมดาที่ออกไปแล้ว (ไม่นับ Score+ Live)",
        )
        wr_sp_manual = st.number_input(
            "⭐ Score+ Live ที่ออกจาก Deck",
            min_value=0, max_value=deck_sp, key="wr_sp_manual", value=0,
            help="จำนวน Score+ Live card ที่ออกจาก Deck ไปแล้ว",
        )
        wr_non = wr_non_plain + wr_sp_manual  # total non-trigger = plain + Score+

        st.number_input(
            "จำนวนใบที่ออกจาก Deck", min_value=1, max_value=59, value=10,
            key="wr_rand_n_manual",
            help="จำนวนการ์ดที่จะสุ่มออกจาก Deck (สัดส่วนตาม Trigger color ของ Deck)",
        )
        st.button("🎲 สุ่ม Waiting Room", key="btn_rnd_wr_manual",
                  on_click=_random_waiting_room_callback, use_container_width=True)

        waiting = WaitingRoom(
            trigger_counts={
                Color.RED: wr_red, Color.BLUE: wr_blue, Color.GREEN: wr_green,
                Color.YELLOW: wr_yellow, Color.PURPLE: wr_purple, Color.PINK: wr_pink,
            },
            all_trigger=wr_all,
            non_trigger=wr_non,
            score_plus_count=wr_sp_manual,
        )
        wr_total = waiting.total()
        _all_out = wr_total
        _remaining_in_deck = total - _all_out
        if wr_sp_manual > wr_non:
            st.warning(
                f"⚠️ Score+ Live ที่ออกไป ({wr_sp_manual} ใบ) มากกว่า Non-Trigger ใน Waiting Room ({wr_non} ใบ) — "
                "Score+ Live card เป็น Non-Trigger ด้วย กรุณาตรวจสอบค่า Non-Trigger"
            )
        else:
            _sp_note = f" (รวม Score+ Live {wr_sp_manual} ใบ)" if wr_sp_manual > 0 else ""
            st.info(f"การ์ดที่ออกจาก Deck = **{_all_out}** ใบ{_sp_note} | คงเหลือใน Deck = **{max(0, _remaining_in_deck)}** ใบ")

    with col2:
        st.header("🎭 Stage Members")
        st.caption("Basic Hearts บนเวที + จำนวน Blade รวม")

        blade_count = st.number_input(
            "🔋 จำนวน Blade รวม (= จำนวนการ์ดที่จะจั่วใน Yell)",
            min_value=0, max_value=60, value=0, key="blade_count",
        )
        st.markdown("**Basic Hearts** (หัวใจที่ได้แน่จาก Member บนเวที)")
        sb_red = st.number_input(color_label(Color.RED), min_value=0, max_value=30, key="sb_red", value=0)
        sb_blue = st.number_input(color_label(Color.BLUE), min_value=0, max_value=30, key="sb_blue", value=0)
        sb_green = st.number_input(color_label(Color.GREEN), min_value=0, max_value=30, key="sb_green", value=0)
        sb_yellow = st.number_input(color_label(Color.YELLOW), min_value=0, max_value=30, key="sb_yellow", value=0)
        sb_purple = st.number_input(color_label(Color.PURPLE), min_value=0, max_value=30, key="sb_purple", value=0)
        sb_pink = st.number_input(color_label(Color.PINK), min_value=0, max_value=30, key="sb_pink", value=0)

        stage = StageMembers(
            basic_hearts={
                Color.RED: sb_red, Color.BLUE: sb_blue, Color.GREEN: sb_green,
                Color.YELLOW: sb_yellow, Color.PURPLE: sb_purple, Color.PINK: sb_pink,
            },
            blade_count=blade_count,
        )
        st.info(f"Basic Hearts รวม = **{stage.total_basic_hearts()}** | Yell draws = **{blade_count}**")

    st.divider()

    # ── Live Cards (manual mode) ───────────────────────────────────────────
    st.header("🎵 Live Card(s) ที่จะเล่น")
    st.caption("กำหนด required hearts ของ Live แต่ละใบ (สูงสุด 3 Live ต่อเทิร์น)")

    if "n_lives" not in st.session_state:
        st.session_state.n_lives = 1
    col_nl, _ = st.columns([1, 3])
    with col_nl:
        n_lives = st.selectbox("จำนวน Live ที่จะเล่น", options=[1, 2, 3], key="n_lives")

    _defaults = [
        {"name": "Live 1", "hearts": {}},
        {"name": "Live 2", "hearts": {}},
        {"name": "Live 3", "hearts": {}},
    ]
    lives = []
    live_cols = st.columns(n_lives)
    _card_options = [CUSTOM_LIVE_OPTION] + [c.label() for c in st.session_state.get("live_cards", [])]
    for i in range(n_lives):
        with live_cols[i]:
            st.subheader(f"Live #{i+1}")
            st.selectbox(
                "เลือกจาก DB (หรือกำหนดเอง)",
                options=_card_options,
                index=0,
                key=f"live_select_{i}",
                on_change=_apply_live_card_to_form,
                args=(i,),
                help="เลือก Live จากรายการเพื่อเติม required hearts อัตโนมัติ",
            )
            _sel_m = st.session_state.get(f"live_select_{i}", "")
            if _sel_m and _sel_m != CUSTOM_LIVE_OPTION:
                _lc_m = next((c for c in st.session_state.get("live_cards", []) if c.label() == _sel_m), None)
                _img_m = _lc_m.image if _lc_m and _lc_m.image else None
                if _img_m:
                    st.image(_card_img_src(_img_m), use_container_width=True)
            name_key = f"live_name_{i}"
            if name_key not in st.session_state:
                st.session_state[name_key] = _defaults[i]["name"] if i < len(_defaults) else f"Live {i+1}"
            for color in HEART_COLORS + [Color.GRAY]:
                k = f"live_{i}_{color.value}"
                if k not in st.session_state:
                    st.session_state[k] = 0
            name = st.text_input("ชื่อ Live", key=name_key)
            req = {}
            for color in HEART_COLORS + [Color.GRAY]:
                n = st.number_input(
                    color_label(color), min_value=0, max_value=20,
                    key=f"live_{i}_{color.value}",
                )
                if n > 0:
                    req[color] = n
            lives.append(LiveRequirement(name=name, required_hearts=req))

# ── Combined requirements summary (both modes) ────────────────────────────
combined_req: dict = {}
for lv in lives:
    for c, n in lv.required_hearts.items():
        combined_req[c] = combined_req.get(c, 0) + n
if combined_req:
    summary = "  ".join(
        f"{color_label(c)}: **{n}**"
        for c, n in combined_req.items()
    )
    _blade_display = st.session_state.get("ov_blade") or st.session_state.get("blade_count") or 0
    st.info(
        f"Required hearts รวม: {summary}  |  Total = **{sum(combined_req.values())}**"
        f"  |  ⚡ Yell (Blade) = **{_blade_display}**"
    )

st.divider()

# ==========================================================================
# CALCULATE
# ==========================================================================
# reshuffle_pool = waiting ลบการ์ดที่ไม่ถูก shuffle กลับออก:
#   - มือ (hand) ไม่กลับ
#   - Stage Member ไม่กลับ
#   - Live card ที่จะเล่น ไม่กลับ
#   - Live card ที่สำเร็จแล้ว ไม่กลับ
_unknown_sample_calc = st.session_state.get("_wr_unknown_sample") or _empty_counts()
_n_hand_calc = st.session_state.get("wr_hand_n") or 0
_n_unknown_calc = _n_hand_calc + (st.session_state.get("wr_extra_n") or 0)
_hand_ratio = _n_hand_calc / _n_unknown_calc if _n_unknown_calc > 0 else 0
_hand_sample: dict = {
    k: round(v * _hand_ratio) for k, v in _unknown_sample_calc.items()
}
_hand_sp = _hand_sample.get("score_plus_drawn", 0)
_hand_non_total = _hand_sample.get("non", 0) + _hand_sp

# คำนวณ trigger ของการ์ดที่ไม่ถูก shuffle กลับ (Stage + Live slots + Live สำเร็จ)
def _fixed_cards_trigger_counts() -> dict:
    """คืน {color_value: count} ของ trigger จากการ์ดที่ไม่ถูก reshuffle กลับ"""
    _idx = st.session_state.get("card_index", {})
    counts: dict = {c.value: 0 for c in Color.trigger_colors()}
    counts["all"] = 0
    counts["non"] = 0
    card_keys = []
    for _si in range(5):
        _k = st.session_state.get(f"stage_slot_{_si}", "")
        if _k:
            card_keys.append(_k)
    for _li in range(3):
        _k = st.session_state.get(f"live_slot_{_li}", "")
        if _k:
            card_keys.append(_k)
    _done_n = st.session_state.get("wr_done_live_count", 0)
    for _di in range(_done_n):
        _k = st.session_state.get(f"wr_done_live_{_di}", "")
        if _k:
            card_keys.append(_k)
    for _k in card_keys:
        _card = _idx.get(_k) or _idx.get(strip_rarity_suffix(_k))
        if _card is None:
            counts["non"] += 1
            continue
        tc = getattr(_card, "trigger_color", None)
        if tc and tc in counts:
            counts[tc] += 1
        elif tc == "all":
            counts["all"] += 1
        else:
            counts["non"] += 1
    return counts

_fixed_trigger = _fixed_cards_trigger_counts()

_reshuffle_pool = WaitingRoom(
    trigger_counts={
        c: max(0, waiting.trigger_counts.get(c, 0)
               - _hand_sample.get(c.value, 0)
               - _fixed_trigger.get(c.value, 0))
        for c in Color.trigger_colors()
    },
    all_trigger=max(0, waiting.all_trigger
                    - _hand_sample.get("all", 0)
                    - _fixed_trigger.get("all", 0)),
    non_trigger=max(0, waiting.non_trigger
                    - _hand_non_total
                    - _fixed_trigger.get("non", 0)),
    score_plus_count=max(0, waiting.score_plus_count - _hand_sp),
)
state = GameState(deck=deck, waiting_room=waiting, stage=stage, lives=lives, reshuffle_pool=_reshuffle_pool)

col_btn1, col_btn2 = st.columns([1, 3])
with col_btn1:
    calc_btn = st.button("🎲 คำนวณความน่าจะเป็น", type="primary", use_container_width=True)
with col_btn2:
    run_mc = st.checkbox("รัน Monte Carlo Simulation ด้วย", value=True)
    mc_trials = st.select_slider(
        "จำนวน trials (Monte Carlo)",
        options=[1_000, 5_000, 10_000, 20_000, 50_000, 100_000],
        value=20_000,
    )

if calc_btn:
    errors = deck.validate()
    if errors:
        for e in errors:
            st.error(e)
    elif _all_out > total:
        st.error(f"⚠️ การ์ดที่ออกจาก Deck ({_all_out} ใบ) เกินจำนวน Deck ({total} ใบ) — กรุณาตรวจสอบ Waiting Room")
    elif not combined_req:
        st.warning("กรุณาเลือก Live Card อย่างน้อย 1 ใบ (หรือกรอก required hearts)")
    else:
        st.subheader("📊 ผลการคำนวณ")

        remaining = state.remaining_deck()
        _needed = state.hearts_needed_from_yell()
        _total_need_from_yell = sum(_needed.values())

        # ── Heart breakdown table ──────────────────────────────────────────
        _heart_rows = []
        for c in HEART_COLORS + [Color.GRAY]:
            req = combined_req.get(c, 0)
            if req == 0:
                continue
            still_need = _needed.get(c, 0)
            emoji = COLOR_EMOJI.get(c, "")
            if c == Color.GRAY:
                have_stage = req - still_need
                label = f"{emoji} Gray (any)"
            else:
                have_stage = stage.hearts_for_color(c)
                label = f"{emoji} {COLOR_LABELS_TH.get(c, c.value)}"
            need_from_yell = still_need
            status = "✅ ครบ" if need_from_yell == 0 else f"⚡ ขาด {need_from_yell}"
            _heart_rows.append({
                "หัวใจ": label,
                "ต้องการ": req,
                "Stage มี": have_stage,
                "ต้องได้จาก Yell": need_from_yell,
                "": status,
            })

        if _heart_rows:
            st.dataframe(
                pd.DataFrame(_heart_rows),
                hide_index=True,
                use_container_width=True,
            )

        # ── Summary metrics ────────────────────────────────────────────────
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        col_r1.metric("Deck ที่เหลือ", f"{max(0, _remaining_in_deck)} ใบ")
        col_r2.metric("Blade (จั่วได้)", f"{blade_count} ใบ")
        col_r3.metric("ต้องได้จาก Yell", f"{_total_need_from_yell} หัวใจ")
        col_r4.metric("Required รวม", f"{sum(combined_req.values())} หัวใจ")

        _will_reshuffle = blade_count > remaining.total()
        if _will_reshuffle:
            _wr_size = _reshuffle_pool.total()
            st.warning(
                f"⚠️ **Mid-Yell Reshuffle** — Deck เหลือ {remaining.total()} ใบ แต่ต้อง Yell {blade_count} ใบ "
                f"→ จะ reshuffle Waiting Room ({_wr_size} ใบ) ระหว่าง Yell\n\n"
                f"Exact Hypergeometric ไม่รองรับกรณีนี้ — **ใช้ผล Monte Carlo เป็นหลัก**"
            )

        with st.spinner("กำลังคำนวณ Hypergeometric Probability..."):
            exact = calculate_live_success_probability(state)

        if run_mc:
            with st.spinner(f"รัน Monte Carlo {mc_trials:,} trials..."):
                sim = simulate_live(state, trials=mc_trials, seed=42)
        else:
            sim = None

        if _will_reshuffle:
            # Reshuffle case: ชูผล MC เป็นหลัก, Exact เป็นข้อมูลอ้างอิงเสริม
            if sim:
                st.markdown("### 🎲 โอกาสสำเร็จ (Monte Carlo)")
                _prob_bar(sim.probability)
                st.caption(f"สำเร็จ {sim.successes:,} / {sim.trials:,} trials · รองรับ Mid-Yell Reshuffle")

            with st.expander("🎯 Exact Hypergeometric (อ้างอิงเท่านั้น — ไม่รองรับ Reshuffle)"):
                _prob_bar(exact.probability)
                st.caption(
                    f"จาก {exact.total_cases:,} combinations · สำเร็จ {exact.favorable_cases:,} combinations\n\n"
                    f"⚠️ ค่านี้คำนวณจาก deck ที่เหลืออยู่เท่านั้น ไม่ได้รวม Waiting Room ที่จะ reshuffle เข้ามา "
                    f"จึง{'ต่ำ' if sim and exact.percent() < sim.percent() else 'สูง'}กว่าความเป็นจริง"
                )
                if sim:
                    diff = abs(sim.percent() - exact.percent())
                    st.caption(f"ต่างจาก Monte Carlo = **{diff:.2f}%**")
        else:
            # ปกติ: แสดงทั้งคู่พร้อม diff
            st.markdown("### 🎯 โอกาสสำเร็จ (Exact Hypergeometric)")
            _prob_bar(exact.probability)
            st.caption(
                f"จาก {exact.total_cases:,} combinations ที่เป็นไปได้ "
                f"→ สำเร็จ {exact.favorable_cases:,} combinations"
            )

            if sim:
                st.markdown(f"### 🎲 โอกาสสำเร็จ (Monte Carlo, {mc_trials:,} trials)")
                _prob_bar(sim.probability)
                diff = abs(sim.percent() - exact.percent())
                _diff_note = (
                    "✅ ใกล้เคียงกันมาก — ผลน่าเชื่อถือ" if diff < 1.0
                    else f"⚠️ ต่างกัน {diff:.2f}% — ลองเพิ่ม trials เพื่อความแม่นยำ"
                )
                st.caption(
                    f"สำเร็จ {sim.successes:,} / {sim.trials:,} trials · "
                    f"ต่างจาก Exact = {diff:.2f}%  |  {_diff_note}"
                )
                _render_failure_breakdown(sim)

        # ── Score+ probability ────────────────────────────────────────────
        # Score+ ติดอยู่กับ Live card ใน Deck — เมื่อ Yell เปิดเจอ Live card ที่มี Score+
        # → ได้คะแนน bonus นั้นทันที
        if remaining.score_plus_count > 0:
            st.markdown("---")
            st.markdown("#### ⭐ Score+")
            _sp_prob = calculate_score_plus_probability(remaining, blade_count)
            _sp_col1, _sp_col2, _ = st.columns([1, 1, 2])
            with _sp_col1:
                st.metric(
                    label="โอกาสได้ Score+",
                    value=f"{_sp_prob * 100:.1f}%",
                    help=(
                        f"P(Yell เจอ Score+ Live card ≥ 1 ใบ)\n"
                        f"Score+ Live ใน Deck: {remaining.score_plus_count} ใบ · "
                        f"Deck เหลือ: {remaining.total()} ใบ · Blade: {blade_count} ใบ"
                    ),
                )
            with _sp_col2:
                st.metric(label="Score+ Live ใน Deck", value=f"{remaining.score_plus_count} ใบ")

        # ── Non-Trigger Sensitivity Analysis ──────────────────────────────
        _non_in_deck_total = deck.non_trigger
        if _non_in_deck_total > 0:
            st.markdown("---")
            st.markdown("#### 📉 ผลกระทบของ Non-Trigger ต่อโอกาสสำเร็จ")
            st.caption(
                "จำลองสถานการณ์: กำหนดจำนวนการ์ดที่ออกจาก Deck รวม แล้วดูว่า "
                "Non-Trigger ที่เหลือใน Deck แต่ละระดับ ส่งผลต่อโอกาสสำเร็จอย่างไร"
            )

            _current_total_out = waiting.total()
            _sens_max = deck.total() - 1
            _sens_total_out = st.number_input(
                "จำนวนการ์ดที่ออกจาก Deck รวม (ในสถานการณ์จำลอง)",
                min_value=0,
                max_value=_sens_max,
                value=min(_current_total_out, _sens_max),
                step=1,
                key="sens_total_out",
                help=(
                    f"ค่าปัจจุบัน = {_current_total_out} ใบ (จาก Waiting Room ที่กรอก) "
                    "— ปรับเพื่อจำลองว่าถ้าการ์ดออกไปมากหรือน้อยกว่านี้จะเป็นอย่างไร"
                ),
            )

            _sens_mc_trials = mc_trials

            with st.spinner(
                f"คำนวณ {_non_in_deck_total + 1} กรณี (total_out={_sens_total_out}) "
                f"× Monte Carlo {_sens_mc_trials:,} trials..."
            ):
                _sens_rows = compute_non_trigger_sensitivity(
                    state,
                    total_out=_sens_total_out,
                    mc_trials=_sens_mc_trials,
                    mc_seed=42,
                )

            if not _sens_rows:
                st.warning("ไม่มีกรณีที่เป็นไปได้สำหรับจำนวนการ์ดออกที่กำหนด — ลองปรับค่า")
            else:
                # หา row ปัจจุบัน (is_current)
                _current_rows = [r for r in _sens_rows if r["is_current"]]
                _base_exact = _current_rows[0]["exact_pct"] if _current_rows else _sens_rows[0]["exact_pct"]
                _base_mc = _current_rows[0]["mc_pct"] if _current_rows else _sens_rows[0]["mc_pct"]

                # ── กราฟเส้น ──────────────────────────────────────────────
                _chart_df = pd.DataFrame({
                    "Non-Trigger คงเหลือใน Deck (ใบ)": [r["non_remaining"] for r in _sens_rows],
                    "Exact (%)": [r["exact_pct"] for r in _sens_rows],
                    "Monte Carlo (%)": [r["mc_pct"] for r in _sens_rows],
                }).set_index("Non-Trigger คงเหลือใน Deck (ใบ)")
                st.line_chart(_chart_df, color=["#1976d2", "#e53935"])

                if _current_rows:
                    _cur = _current_rows[0]
                    st.info(
                        f"▶ สถานการณ์ปัจจุบัน: Non-Trigger ใน Deck = **{_cur['non_remaining']} ใบ** | "
                        f"Exact = **{_cur['exact_pct']:.2f}%** | MC = **{_cur['mc_pct']:.2f}%**"
                    )

                # ── ตาราง ──────────────────────────────────────────────────
                _table_rows = []
                for r in _sens_rows:
                    _delta_exact = r["exact_pct"] - _base_exact
                    _delta_mc = r["mc_pct"] - _base_mc
                    _is_cur = r["is_current"]
                    _table_rows.append({
                        "Non ใน Deck": f"{'▶ ' if _is_cur else ''}{r['non_remaining']} ใบ{'  (ปัจจุบัน)' if _is_cur else ''}",
                        "Non ออกไป": f"{r['non_wr']} ใบ",
                        "Trigger ออกไป": f"{r['trigger_wr']} ใบ",
                        "Deck เหลือ": f"{r['deck_remaining']} ใบ",
                        "Exact (%)": f"{r['exact_pct']:.2f}%",
                        "Δ Exact": ("—" if _is_cur else f"{_delta_exact:+.2f}%"),
                        "Monte Carlo (%)": f"{r['mc_pct']:.2f}%",
                        "Δ MC": ("—" if _is_cur else f"{_delta_mc:+.2f}%"),
                    })
                with st.expander("📋 ตารางรายละเอียด", expanded=False):
                    st.dataframe(
                        pd.DataFrame(_table_rows),
                        hide_index=True,
                        use_container_width=True,
                    )

        # Breakdown
        with st.expander("🔍 Deck ที่เหลืออยู่ (Remaining Deck)"):
            rows = []
            for c in HEART_COLORS:
                if remaining.count(c) > 0:
                    rows.append({"ประเภท": color_label(c), "จำนวน": remaining.count(c)})
            if remaining.all_trigger > 0:
                rows.append({"ประเภท": color_label(Color.ALL), "จำนวน": remaining.all_trigger})
            if remaining.non_trigger > 0:
                rows.append({"ประเภท": "⬛ Non-Trigger", "จำนวน": remaining.non_trigger})
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ==========================================================================
# FOOTER
# ==========================================================================
st.divider()
st.caption(
    "🛠️ สร้างด้วย Python + Streamlit · "
    "Math: Multivariate Hypergeometric Distribution · "
    "สอบทานด้วย Monte Carlo Simulation"
)
