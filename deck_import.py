"""
Deck import — แปลง deck code จาก decklog-en.bushiroad.com (หรือข้อความ paste)
ให้กลายเป็น DeckComposition พร้อมใส่ใน Streamlit form.

Pipeline:
  deck code → fetch_deck_from_decklog()  ┐
  paste text → parse_pasted_deck_list()  ┴→ List[DeckEntry]
  DeckEntry + card_index (จาก card_db.get_card_index) → compose_deck_from_entries()
  → (DeckComposition, warnings)
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from card_db import DeckCard, LiveCard, normalize_card_no, strip_rarity_suffix
from models import Color, DeckComposition


DECKLOG_BASE = "https://decklog-en.bushiroad.com"
# Decklog API — reverse-engineered จาก Vue app (method `__ap()` ใน app.js คืน "app" หรือ "app-ja")
# POST /system/app-ja/api/view/<code>  → คืน deck เต็ม (มี field "list")
# POST /system/app/api/view/<code>     → คืนเฉพาะ metadata (ไม่มี list) — ลอง fallback
# Response schema: {"id":..., "deck_id":"1385T", "title":..., "list":[{card_number, num, ...}, ...]}
DECKLOG_API_PATHS: Tuple[str, ...] = (
    "/system/app-ja/api/view/{code}",
    "/system/app/api/view/{code}",
)


class DecklogError(RuntimeError):
    """ดึง deck จาก decklog ไม่สำเร็จ (network / format / deck ไม่ public)."""


@dataclass
class DeckEntry:
    card_no: str
    count: int


@dataclass
class DecklogDeck:
    """Deck ที่ดึงจาก decklog พร้อม metadata — ใช้แสดงใน UI."""
    code: str
    title: str
    entries: List[DeckEntry]


# ==========================================================================
# Paste parser
# ==========================================================================
_PASTE_LINE_RE = re.compile(
    r"""
    ^\s*
    (?:
        (?P<count1>\d+)\s*[x×*]?\s+(?P<no1>\S+)   # "3 LL-bp1-001-R+"  or "3x LL-..."
      | (?P<no2>\S+)\s*[x×*]\s*(?P<count2>\d+)   # "LL-bp1-001-R+ x3"
      | (?P<no3>\S+)\s*[,\t]\s*(?P<count3>\d+)   # "LL-bp1-001-R+, 3"
      | (?P<no4>\S+)                              # "LL-bp1-001-R+"  (count=1)
    )
    \s*$
    """,
    re.VERBOSE,
)


def parse_pasted_deck_list(text: str) -> List[DeckEntry]:
    """
    Parse free-form deck list (หลายบรรทัด) เป็น List[DeckEntry].

    รองรับหลาย format ต่อบรรทัด:
      "3 LL-bp1-001-R+"
      "3x LL-bp1-001-R+"
      "LL-bp1-001-R+ x3"
      "LL-bp1-001-R+, 3"
      "LL-bp1-001-R+"        (นับเป็น 1)
    บรรทัดว่างและบรรทัดที่ขึ้นต้นด้วย '#' หรือ '//' จะถูกข้าม.
    card_no เดียวกันที่ซ้ำกันจะรวม count.
    """
    acc: Dict[str, int] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        m = _PASTE_LINE_RE.match(line)
        if not m:
            continue
        card_no = m.group("no1") or m.group("no2") or m.group("no3") or m.group("no4") or ""
        cnt_str = m.group("count1") or m.group("count2") or m.group("count3") or "1"
        try:
            count = int(cnt_str)
        except ValueError:
            continue
        if not card_no or count <= 0:
            continue
        acc[normalize_card_no(card_no)] = acc.get(normalize_card_no(card_no), 0) + count
    return [DeckEntry(card_no=k, count=v) for k, v in acc.items()]


# ==========================================================================
# Decklog API
# ==========================================================================
_UA = "Mozilla/5.0 (llocg-calculator/1.0)"


def _http_json(url: str, timeout: float = 15.0, data: Optional[bytes] = None) -> object:
    headers = {
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{DECKLOG_BASE}/",
    }
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, headers=headers, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise DecklogError(f"Decklog ตอบกลับที่ไม่ใช่ JSON: {e}") from e


def _entries_from_decklog_payload(payload: object) -> List[DeckEntry]:
    """
    แปลง JSON response ของ decklog เป็น List[DeckEntry] ของ main deck.

    Schema จริงของ decklog (reverse-engineered):
        {
          "id": ..., "deck_id": "1385T", "title": "...",
          "game_title_id": 109,              # 109 = LLOCG
          "list":     [{card_number, num, type:1, card_kind:"M|L", ...}, ...],   # main 60
          "sub_list": [{card_number, num, type:2, card_kind:"E", ...}, ...],     # energy 12 (แยก)
          ...
        }

    เรานับเฉพาะ `list` (main deck) — Energy deck อยู่ใน `sub_list` ต่างหาก
    (ตามกฎ LLOCG main deck 60 ใบ = Member + Live เท่านั้น)
    """
    raw_list = None
    if isinstance(payload, dict):
        raw_list = payload.get("list")
    if not isinstance(raw_list, list):
        return []
    entries: Dict[str, int] = {}
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        # ถ้ามี type ให้ข้าม sub/energy (type != 1)
        type_val = item.get("type")
        if type_val is not None and type_val != 1:
            continue
        card_no = item.get("card_number") or item.get("card_no")
        if not card_no:
            continue
        card_no = normalize_card_no(str(card_no))
        try:
            count = int(item.get("num", 1))
        except (ValueError, TypeError):
            count = 1
        if count <= 0:
            continue
        entries[card_no] = entries.get(card_no, 0) + count
    return [DeckEntry(card_no=k, count=v) for k, v in entries.items()]


def fetch_deck_from_decklog(code: str, timeout: float = 15.0) -> DecklogDeck:
    """
    ดึง deck จาก decklog-en.bushiroad.com ด้วย deck code.

    Method = POST (ตรงกับที่ Vue app ใช้จริง).
    ลอง endpoint ตามลำดับจนกว่าจะเจอที่มี field "list" ไม่ว่าง.

    Returns DecklogDeck (code + title + entries).
    Raises DecklogError ถ้าทุก endpoint ไม่คืนข้อมูลที่ parse ได้.
    """
    code = (code or "").strip()
    if not code:
        raise DecklogError("กรุณาใส่ deck code")
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,20}", code):
        raise DecklogError("Deck code มีอักขระที่ไม่ถูกต้อง")
    encoded = urllib.parse.quote(code, safe="")
    last_error: Optional[Exception] = None
    for path_tmpl in DECKLOG_API_PATHS:
        url = DECKLOG_BASE + path_tmpl.format(code=encoded)
        try:
            # POST body ว่าง — Vue app ก็ POST ไม่ส่ง body, deck code อยู่ใน URL อยู่แล้ว
            payload = _http_json(url, timeout=timeout, data=b"")
        except (urllib.error.URLError, DecklogError) as e:
            last_error = e
            continue
        except Exception as e:  # noqa: BLE001
            last_error = e
            continue
        entries = _entries_from_decklog_payload(payload)
        if entries:
            title = ""
            if isinstance(payload, dict):
                title = str(payload.get("title") or "")
            return DecklogDeck(code=code, title=title, entries=entries)
    if last_error:
        raise DecklogError(
            f"ดึง deck '{code}' จาก decklog ไม่สำเร็จ: {last_error}"
        )
    raise DecklogError(
        f"ไม่พบ deck '{code}' หรือ decklog คืนข้อมูลว่าง — "
        "ตรวจว่า deck เป็น public และ code ถูกต้อง"
    )


# ==========================================================================
# Compose DeckComposition
# ==========================================================================
def compose_deck_from_entries(
    entries: List[DeckEntry],
    card_index: Dict[str, DeckCard],
    live_cards: Optional[List[LiveCard]] = None,
) -> Tuple[DeckComposition, List[str]]:
    """
    รวม DeckEntry เป็น DeckComposition โดย lookup trigger_color จาก card_index.

    live_cards: ถ้าส่งมา จะนับ Live card ใน deck ที่มี Score+ effect ด้วย
                (score_plus_count ใน DeckComposition)

    Returns (composition, warnings).
    """
    trigger_counts: Dict[Color, int] = {c: 0 for c in Color.trigger_colors()}
    all_trigger = 0
    non_trigger = 0
    warnings: List[str] = []
    total_counted = 0

    # Build Score+ lookup: card_no → score_plus value
    sp_lookup: Dict[str, int] = {}
    if live_cards:
        for lc in live_cards:
            if lc.score_plus > 0:
                sp_lookup[lc.card_no] = lc.score_plus

    score_plus_count = 0

    for e in entries:
        # ลอง lookup ด้วย full card_no ก่อน (เช่น PL!SP-bp1-005-R)
        # ถ้าไม่เจอ ลอง strip rarity suffix แล้ว lookup ด้วย base Number (เช่น PL!SP-bp1-005)
        card = card_index.get(e.card_no) or card_index.get(strip_rarity_suffix(e.card_no))
        if card is None:
            warnings.append(f"ไม่พบ card_no ใน DB: {e.card_no} (×{e.count})")
            continue
        total_counted += e.count
        tc = card.trigger_color
        if tc is None:
            non_trigger += e.count
        elif tc == Color.ALL:
            all_trigger += e.count
        elif tc in trigger_counts:
            trigger_counts[tc] += e.count
        else:
            warnings.append(
                f"{e.card_no}: blade_heart={tc.value} ไม่ใช่สี trigger ปกติ — นับเป็น Non-Trigger"
            )
            non_trigger += e.count

        # นับ Score+ Live cards ใน deck (ไม่ขึ้นกับ trigger_color)
        if e.card_no in sp_lookup:
            score_plus_count += e.count

    composition = DeckComposition(
        trigger_counts=trigger_counts,
        all_trigger=all_trigger,
        non_trigger=non_trigger,
        score_plus_count=score_plus_count,
    )
    if total_counted != 60:
        warnings.append(
            f"Deck รวม {total_counted} ใบ (ตามกฎ LLOCG ต้อง 60 ใบ)"
        )
    return composition, warnings
