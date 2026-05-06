"""
Live card database — Assets-first + web-scrape fallback.

Strategy (ลำดับความสำคัญ):
  1. Assets/LiveCardTable.json + Assets/MemberCardTable.json = primary source
     (ข้อมูลครบถ้วน, Score+ ถูกต้อง, รูปการ์ด local)
  2. bundled snapshot data/live_cards.json = fallback ถ้าไม่มี Assets
  3. fetch_live_cards_from_web() = optional refresh จาก llocg-th.vercel.app
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from models import Color, LiveRequirement


CARDS_PAGE_URL = "https://llocg-th.vercel.app/cards"
CHUNK_URL_TEMPLATE = "https://llocg-th.vercel.app/_next/static/chunks/{name}.js"
SNAPSHOT_PATH = Path(__file__).parent / "data" / "live_cards.json"
CARD_INDEX_PATH = Path(__file__).parent / "data" / "cards_index.json"

ASSETS_DIR = Path(__file__).parent / "Assets"
ASSETS_LIVE_JSON = ASSETS_DIR / "LiveCardTable.json"
ASSETS_MEMBER_JSON = ASSETS_DIR / "MemberCardTable.json"
ASSETS_IMAGES_LIVE = ASSETS_DIR / "Images" / "Live"
ASSETS_IMAGES_MEMBER = ASSETS_DIR / "Images" / "Member"

# Normalize card_no ให้ตรงกันทั้ง DB และ decklog:
#   - full-width plus (＋ U+FF0B) → ASCII +
#   - space ก่อน + หรือ ＋ (decklog ส่ง "R +" แต่ DB เก็บ "R＋") → ลบ space
def normalize_card_no(card_no: str) -> str:
    return card_no.replace(" ＋", "＋").replace("＋", "+").replace(" +", "+")


def strip_rarity_suffix(card_no: str) -> str:
    """
    ตัด rarity suffix ออกจาก card_no ของ decklog เพื่อ lookup ใน Assets.

    decklog ส่ง: PL!SP-bp1-005-R, PL!SP-bp4-005-R+, PL!SP-bp4-023-L
    Assets เก็บ: PL!SP-bp1-005 (Number field), แล้ว full = PL!SP-bp1-005-P

    Rarity suffixes: -R, -R+, -N, -L, -SD, -P, -PR, -SEC, -AR, -P2, -R2 ฯลฯ
    Pattern: ตัดส่วน '-' + [A-Za-z0-9+]+ ท้ายสุด
    """
    import re as _re
    m = _re.match(r'^(.+)-([A-Za-z0-9+]{1,5})$', card_no)
    return m.group(1) if m else card_no

# card_type ในข้อมูลต้นทางเป็นภาษาญี่ปุ่น — แมพเป็น tag สั้นใน snapshot
_CARD_TYPE_MAP: Dict[str, str] = {
    "ライブ": "live",
    "メンバー": "member",
    "エネルギー": "energy",
}

# เว็บต้นทางใช้ "grey", models.py ใช้ Color.GRAY — แมพตรงๆ
_WEB_TO_COLOR: Dict[str, Color] = {
    "red": Color.RED,
    "blue": Color.BLUE,
    "green": Color.GREEN,
    "yellow": Color.YELLOW,
    "purple": Color.PURPLE,
    "pink": Color.PINK,
    "grey": Color.GRAY,
    "gray": Color.GRAY,
    "all": Color.ALL,
}


@dataclass
class DeckCard:
    """
    การ์ดที่อยู่ใน deck ได้ (Member/Live/Energy).
    ใช้สำหรับ import deck จาก decklog — ต้องรู้แค่ card_no → trigger_color เพื่อ
    aggregate เป็น DeckComposition.

    trigger_color: None = Non-Trigger (blade_heart ว่างใน DB)
                   Color.ALL = All Trigger
                   สีอื่นๆ = trigger สีนั้น
    """
    name: str
    card_no: str
    card_type: str                       # "member" | "live" | "energy"
    trigger_color: Optional[Color] = None
    blade: int = 0
    base_heart: Dict[Color, int] = field(default_factory=dict)
    series: str = ""
    image: str = ""

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "card_no": self.card_no,
            "card_type": self.card_type,
            "trigger_color": self.trigger_color.value if self.trigger_color else None,
            "blade": self.blade,
            "base_heart": {c.value: n for c, n in self.base_heart.items()},
            "series": self.series,
            "image": self.image,
        }

    @classmethod
    def from_json(cls, d: dict) -> "DeckCard":
        tc = d.get("trigger_color")
        return cls(
            name=d["name"],
            card_no=normalize_card_no(d["card_no"]),
            card_type=d.get("card_type", ""),
            trigger_color=Color(tc) if tc else None,
            blade=int(d.get("blade") or 0),
            base_heart={Color(k): int(v) for k, v in d.get("base_heart", {}).items()},
            series=d.get("series", "") or "",
            image=d.get("image", "") or "",
        )


@dataclass
class LiveCard:
    """
    A Live card with required hearts parsed from the Thai DB.
    `required_hearts` ใช้ key เป็น Color enum ส่งต่อเข้า LiveRequirement ได้เลย.
    """
    name: str
    card_no: str
    required_hearts: Dict[Color, int] = field(default_factory=dict)
    score: int = 0
    score_plus: int = 0   # Score+ ที่ได้เมื่อ Yell เจอ Non-Trigger (0 = ไม่มี)
    special_heart: str = ""
    series: str = ""
    product: str = ""
    image: str = ""

    def to_requirement(self) -> LiveRequirement:
        """แปลงเป็น LiveRequirement ที่ใช้ใน GameState ได้เลย."""
        return LiveRequirement(
            name=self.name,
            required_hearts=dict(self.required_hearts),
            score=self.score,
        )

    def label(self) -> str:
        """แสดงผลบน dropdown — ชื่อ + card_no."""
        return f"{self.name}  [{self.card_no}]"

    # ---- serialization ----
    def to_json(self) -> dict:
        return {
            "name": self.name,
            "card_no": self.card_no,
            "required_hearts": {c.value: n for c, n in self.required_hearts.items()},
            "score": self.score,
            "score_plus": self.score_plus,
            "special_heart": self.special_heart,
            "series": self.series,
            "product": self.product,
            "image": self.image,
        }

    @classmethod
    def from_json(cls, d: dict) -> "LiveCard":
        hearts = {Color(k): int(v) for k, v in d.get("required_hearts", {}).items()}
        # อ่าน score_plus จาก field โดยตรงถ้ามี (snapshot ใหม่), fallback re-parse จาก special_heart
        saved_sp = d.get("score_plus")
        score_plus = int(saved_sp) if saved_sp is not None else _parse_score_plus(d.get("special_heart", "") or "")
        return cls(
            name=d["name"],
            card_no=d["card_no"],
            required_hearts=hearts,
            score=int(d.get("score") or 0),
            score_plus=score_plus,
            special_heart=d.get("special_heart", "") or "",
            series=d.get("series", "") or "",
            product=d.get("product", "") or "",
            image=d.get("image", "") or "",
        )


# ==========================================================================
# Parsing
# ==========================================================================
def parse_required_heart(s: str) -> Dict[Color, int]:
    """
    Parse required_heart string from the Thai DB into {Color: int}.

    Format: comma-separated `color:count` pairs.
        >>> parse_required_heart("red:5,grey:3") == {Color.RED: 5, Color.GRAY: 3}
        True
        >>> parse_required_heart("grey:4") == {Color.GRAY: 4}
        True
        >>> parse_required_heart("") == {}
        True

    Unknown colors are skipped silently; malformed pairs are skipped.
    """
    if not s or not s.strip():
        return {}
    out: Dict[Color, int] = {}
    for part in s.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        color_str, _, n_str = part.partition(":")
        color_str = color_str.strip().lower()
        n_str = n_str.strip()
        if color_str not in _WEB_TO_COLOR:
            continue
        try:
            n = int(n_str)
        except ValueError:
            continue
        if n <= 0:
            continue
        color = _WEB_TO_COLOR[color_str]
        out[color] = out.get(color, 0) + n
    return out


def parse_blade_heart(s: str) -> Optional[Color]:
    """
    Parse blade_heart string จาก Thai DB → trigger color ของการ์ด.

    Format: string เดียว (ไม่ใช่ comma-separated).
        ""       → None (Non-Trigger)
        "all"    → Color.ALL
        "red"..  → Color.RED ...
        "grey"   → Color.GRAY

    Unknown / malformed → None (ถือเป็น Non-Trigger โดย default).
    """
    if not s:
        return None
    key = s.strip().lower()
    if not key:
        return None
    return _WEB_TO_COLOR.get(key)


def _parse_score_plus(special_heart: str, text_card: str = "") -> int:
    """
    Parse Score+ value จาก special_heart และ text_card.

    Cases:
      'Score+1'         → 1  (format ตรงๆ)
      'スコア' หรือ 'score' → ค้นหา 'Score +N' ใน text_card
    """
    s = (special_heart or "").strip()
    # format ตรงๆ เช่น 'Score+1'
    m = re.match(r"Score\+(\d+)", s, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # format ภาษาญี่ปุ่น/lowercase → ค้นหาใน text_card
    if s in ("スコア", "score"):
        text = text_card if isinstance(text_card, str) else " ".join(text_card)
        m2 = re.search(r"Score\s*\+\s*(\d+)", text, re.IGNORECASE)
        if m2:
            return int(m2.group(1))
    return 0


def _coerce_int(v) -> int:
    """DB เก็บ score เป็น int, str, หรือ ว่าง — ทำให้เป็น int เสมอ."""
    if v is None or v == "":
        return 0
    if isinstance(v, int):
        return v
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return 0


# ==========================================================================
# Assets loader (primary source)
# ==========================================================================

# BladeHeart field ใน Assets JSON:
#   "score:1"           → Non-Trigger (score_plus=1)
#   "purple:1"          → Color.PURPLE trigger
#   "all:1"             → Color.ALL trigger
#   "pink:1, draw:1"    → Color.PINK trigger + draw effect
#   ""                  → Non-Trigger (no trigger, no score+)
_ASSETS_COLOR_MAP: Dict[str, Color] = {
    "red":    Color.RED,
    "blue":   Color.BLUE,
    "green":  Color.GREEN,
    "yellow": Color.YELLOW,
    "purple": Color.PURPLE,
    "pink":   Color.PINK,
    "all":    Color.ALL,
}

# Required-heart fields ใน LiveCardTable / MemberCardTable → Color
_ASSETS_HEART_FIELDS: Dict[str, Color] = {
    "Red":    Color.RED,
    "Blue":   Color.BLUE,
    "Green":  Color.GREEN,
    "Yellow": Color.YELLOW,
    "Purple": Color.PURPLE,
    "Pink":   Color.PINK,
    "None":   Color.GRAY,   # "None" = wildcard gray requirement
}


def _parse_assets_bladeheart(bh: str) -> Tuple[Optional[Color], int]:
    """
    แปลง BladeHeart string จาก Assets เป็น (trigger_color, score_plus).

    Examples:
      "purple:1"       → (Color.PURPLE, 0)
      "all:1"          → (Color.ALL, 0)
      "pink:1, draw:1" → (Color.PINK, 0)
      "score:1"        → (None, 1)   ← Non-Trigger + Score+1
      ""               → (None, 0)   ← Non-Trigger
    """
    if not bh or not bh.strip():
        return None, 0
    score_plus = 0
    trigger_color: Optional[Color] = None
    for part in bh.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, _, val = part.partition(":")
        key = key.strip().lower()
        if key == "score":
            score_plus = _coerce_int(val.strip())
        elif key in _ASSETS_COLOR_MAP:
            trigger_color = _ASSETS_COLOR_MAP[key]
        # "draw" → ignored (draw effect ไม่ใช่ trigger color)
    return trigger_color, score_plus


def _assets_image_path(card_type: str, filename: str) -> str:
    """คืน path สัมพัทธ์จาก lovelive_calculator/ ไปยังรูปการ์ด."""
    if card_type == "live":
        return str((ASSETS_IMAGES_LIVE / filename).as_posix())
    return str((ASSETS_IMAGES_MEMBER / filename).as_posix())


def load_from_assets_live() -> List[LiveCard]:
    """
    โหลด Live cards จาก Assets/LiveCardTable.json (UTF-16).

    Fields ที่ใช้:
      Number       → card_no (ไม่มี rarity suffix — ดึงจาก CardSubInfo)
      Name         → name
      Red/Blue/..  → required_hearts
      None         → required_hearts[Color.GRAY]
      Score        → score
      BladeHeart   → trigger_color (ignored สำหรับ Live) + score_plus
      CardSubInfo  → "card_no_full/filename.png/rarity/set"
      Text         → text (เก็บไว้แต่ไม่ใช้ใน calculator)
    """
    if not ASSETS_LIVE_JSON.exists():
        return []
    raw: list = json.loads(ASSETS_LIVE_JSON.read_text(encoding="utf-16"))
    cards: List[LiveCard] = []
    seen: set = set()
    for obj in raw:
        sub = obj.get("CardSubInfo", "")
        parts = sub.split("/") if sub else []
        card_no_full = normalize_card_no(parts[0]) if parts else normalize_card_no(obj.get("Number", ""))
        if not card_no_full or card_no_full in seen:
            continue
        seen.add(card_no_full)

        img_filename = parts[1] if len(parts) > 1 else ""
        img_path = _assets_image_path("live", img_filename) if img_filename else ""

        required: Dict[Color, int] = {}
        for field_name, color in _ASSETS_HEART_FIELDS.items():
            n = _coerce_int(obj.get(field_name, 0))
            if n > 0:
                required[color] = n

        _bh = obj.get("BladeHeart", "") or ""
        _trigger_color, score_plus = _parse_assets_bladeheart(_bh)

        cards.append(LiveCard(
            name=obj.get("Name", "") or "",
            card_no=card_no_full,
            required_hearts=required,
            score=_coerce_int(obj.get("Score", 0)),
            score_plus=score_plus,
            special_heart=_bh,
            series=obj.get("Group", "") or "",
            product=obj.get("Contain", "") or "",
            image=img_path,
        ))
    return cards


def load_from_assets_members() -> List[DeckCard]:
    """
    โหลด Member cards จาก Assets/MemberCardTable.json (UTF-16).
    รวม Live cards ด้วยเพื่อให้ card_index ครอบคลุม deck ทั้งหมด.

    Fields ที่ใช้:
      Number/CardSubInfo → card_no (full with rarity)
      BladeHeart         → trigger_color
      Blade              → blade count
      Pink/Yellow/...    → base_heart
      CardSubInfo        → image filename
    """
    # result เป็น dict แทน list เพื่อ register alias หลาย key ต่อการ์ดหนึ่งใบ
    # key = card_no ที่ต้องการ lookup (อาจมีหลาย alias ต่อการ์ดเดียวกัน)
    result: Dict[str, DeckCard] = {}

    def _load_table(path: Path, card_type: str) -> None:
        if not path.exists():
            return
        raw: list = json.loads(path.read_text(encoding="utf-16"))
        for obj in raw:
            sub = obj.get("CardSubInfo", "")
            parts = sub.split("/") if sub else []
            card_no_full = normalize_card_no(parts[0]) if parts else normalize_card_no(obj.get("Number", ""))
            if not card_no_full:
                continue

            img_filename = parts[1] if len(parts) > 1 else ""
            img_path = _assets_image_path(card_type, img_filename) if img_filename else ""

            _bh = obj.get("BladeHeart", "") or ""
            trigger_color, _sp = _parse_assets_bladeheart(_bh)

            base_heart: Dict[Color, int] = {}
            for field_name, color in _ASSETS_HEART_FIELDS.items():
                if field_name == "None":
                    continue  # base_heart ไม่มี Gray
                n = _coerce_int(obj.get(field_name, 0))
                if n > 0:
                    base_heart[color] = n

            card = DeckCard(
                name=obj.get("Name", "") or "",
                card_no=card_no_full,
                card_type=card_type,
                trigger_color=trigger_color,
                blade=_coerce_int(obj.get("Blade", 0)),
                base_heart=base_heart,
                series=obj.get("Group", "") or "",
                image=img_path,
            )

            # Register ด้วย full card_no (เช่น PL!SP-bp1-005-P)
            if card_no_full not in result:
                result[card_no_full] = card

            # Register alias ด้วย Number (ไม่มี rarity suffix เช่น PL!SP-bp1-005)
            # decklog ส่ง -R, -N, -L ฯลฯ — strip แล้ว lookup ด้วย Number ได้เลย
            base_no = normalize_card_no(obj.get("Number", ""))
            if base_no and base_no not in result:
                result[base_no] = card

    _load_table(ASSETS_MEMBER_JSON, "member")
    _load_table(ASSETS_LIVE_JSON, "live")
    return list(result.values())


def _js_str_to_json(s: str) -> str:
    """แปลง JS string escapes ที่ไม่ valid ใน JSON ให้ใช้งานได้.
    - \\' → '   (JS อนุญาต แต่ JSON ไม่อนุญาต)
    - \\" ที่ embed อยู่ใน string → "  (double-escaped quotes ใน JS bundle)
    """
    return s.replace("\\'", "'").replace('\\"', '"')


def _iter_card_objects(js: str):
    """
    Iterate raw card JSON objects from a Next.js bundle.

    yields dict for each parseable card object (no type filter).

    ความท้าทาย: JS bundle ใช้ escape sequences ที่ไม่ valid ใน JSON เช่น \\' และ \\"
    ซึ่งทำให้ json.loads() fail โดยตรง — แก้ด้วย _js_str_to_json() ก่อน parse
    """
    # anchor บน card_no แทน card_name เพื่อหลีกเลี่ยงกรณีชื่อการ์ดมี \" ฝังอยู่
    pattern = re.compile(
        r'\{(?P<body>[^{}]*?"card_no"\s*:\s*"(?P<card_no>[^"]+)"[^{}]*?)\}',
        re.DOTALL,
    )
    for m in pattern.finditer(js):
        body = m.group("body")
        if '"card_type"' not in body or '"card_name"' not in body:
            continue
        full = "{" + body + "}"
        try:
            yield json.loads(_js_str_to_json(full))
        except json.JSONDecodeError:
            continue


def _extract_live_cards_from_bundle(js: str) -> List[LiveCard]:
    """Extract Live-card entries from a downloaded Next.js chunk."""
    cards: List[LiveCard] = []
    seen = set()
    for obj in _iter_card_objects(js):
        if obj.get("card_type") != "ライブ":
            continue
        card_no = normalize_card_no(obj.get("card_no", "") or "")
        if not card_no or card_no in seen:
            continue
        seen.add(card_no)
        _sh = obj.get("special_heart", "") or ""
        _tc = obj.get("text_card", "") or ""
        cards.append(LiveCard(
            name=obj.get("card_name", "") or "",
            card_no=card_no,
            required_hearts=parse_required_heart(obj.get("required_heart", "") or ""),
            score=_coerce_int(obj.get("score")),
            score_plus=_parse_score_plus(_sh, _tc),
            special_heart=_sh,
            series=obj.get("series", "") or "",
            product=obj.get("product", "") or "",
            image=obj.get("image", "") or "",
        ))
    return cards


def _extract_deck_cards_from_bundle(js: str) -> List[DeckCard]:
    """
    Extract ALL deck-usable cards (Member + Live + Energy) from a bundle.
    ใช้สำหรับสร้าง card index เพื่อ lookup trigger color ตอน import deck.
    """
    cards: List[DeckCard] = []
    seen = set()
    for obj in _iter_card_objects(js):
        jp_type = obj.get("card_type", "")
        tag = _CARD_TYPE_MAP.get(jp_type)
        if tag is None:
            continue
        card_no = normalize_card_no(obj.get("card_no", "") or "")
        if not card_no or card_no in seen:
            continue
        seen.add(card_no)
        cards.append(DeckCard(
            name=obj.get("card_name", "") or "",
            card_no=card_no,
            card_type=tag,
            trigger_color=parse_blade_heart(obj.get("blade_heart", "") or ""),
            blade=_coerce_int(obj.get("blade")),
            base_heart=parse_required_heart(obj.get("base_heart", "") or ""),
            series=obj.get("series", "") or "",
            image=obj.get("image", "") or "",
        ))
    return cards


# ==========================================================================
# Web fetch
# ==========================================================================
def _http_get(url: str, timeout: float = 15.0) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "llocg-calculator/1.0 (+https://github.com/)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _find_chunk_urls(cards_html: str) -> List[str]:
    """Find all /_next/static/chunks/*.js URLs referenced from the /cards page."""
    names = re.findall(r'/_next/static/chunks/([a-f0-9]{16})\.js', cards_html)
    # dedup preserving order
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(CHUNK_URL_TEMPLATE.format(name=n))
    return out


def _fetch_all_chunks(timeout: float) -> List[str]:
    """GET /cards page แล้วดึง JS ของทุก chunk คืนเป็น list of JS strings."""
    html = _http_get(CARDS_PAGE_URL, timeout=timeout)
    chunk_urls = _find_chunk_urls(html)
    if not chunk_urls:
        raise RuntimeError("ไม่พบ JS chunks ในหน้า /cards — layout ของเว็บอาจเปลี่ยน")
    chunks = []
    last_error: Optional[Exception] = None
    for url in chunk_urls:
        try:
            chunks.append(_http_get(url, timeout=timeout))
        except Exception as e:  # noqa: BLE001
            last_error = e
    if not chunks and last_error:
        raise RuntimeError(f"ดึง JS chunks ไม่สำเร็จ: {last_error}")
    return chunks


def fetch_live_cards_from_web(timeout: float = 20.0) -> List[LiveCard]:
    """
    Scrape https://llocg-th.vercel.app/cards for Live card definitions.
    ดึงทุก JS chunk แล้วรวมผล เพื่อให้ได้การ์ดครบทุกใบแม้ข้อมูลกระจายอยู่หลาย chunk.

    Raises:
        RuntimeError: if no Live cards can be extracted (network error / layout change).
    """
    chunks = _fetch_all_chunks(timeout)
    all_cards: List[LiveCard] = []
    seen: set = set()
    for js in chunks:
        if '"card_type":"ライブ"' not in js:
            continue
        for card in _extract_live_cards_from_bundle(js):
            if card.card_no not in seen:
                seen.add(card.card_no)
                all_cards.append(card)
    if not all_cards:
        raise RuntimeError("สแกน JS chunks ครบแล้วแต่ไม่เจอการ์ด Live — format ของเว็บอาจเปลี่ยน")
    return all_cards


def fetch_card_index_from_web(timeout: float = 20.0) -> List[DeckCard]:
    """
    Scrape https://llocg-th.vercel.app/cards for ALL deck-usable cards.
    ดึงทุก JS chunk แล้วรวมผล เพื่อให้ได้การ์ดครบทุกใบ (Member/Live/Energy).
    """
    chunks = _fetch_all_chunks(timeout)
    all_cards: List[DeckCard] = []
    seen: set = set()
    for js in chunks:
        if '"card_type"' not in js:
            continue
        for card in _extract_deck_cards_from_bundle(js):
            if card.card_no not in seen:
                seen.add(card.card_no)
                all_cards.append(card)
    if not all_cards:
        raise RuntimeError("สแกน JS chunks ครบแล้วแต่ไม่เจอการ์ด — format ของเว็บอาจเปลี่ยน")
    return all_cards


# ==========================================================================
# Snapshot I/O
# ==========================================================================
def save_snapshot(cards: List[LiveCard], path: Path = SNAPSHOT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": CARDS_PAGE_URL,
        "count": len(cards),
        "cards": [c.to_json() for c in cards],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_snapshot(path: Path = SNAPSHOT_PATH) -> List[LiveCard]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [LiveCard.from_json(d) for d in data.get("cards", [])]


def save_card_index(cards: List[DeckCard], path: Path = CARD_INDEX_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": CARDS_PAGE_URL,
        "count": len(cards),
        "cards": [c.to_json() for c in cards],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_card_index(path: Path = CARD_INDEX_PATH) -> Dict[str, DeckCard]:
    """Load card index snapshot as a dict keyed by card_no."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: Dict[str, DeckCard] = {}
    for d in data.get("cards", []):
        try:
            card = DeckCard.from_json(d)
        except (KeyError, ValueError):
            continue
        out[normalize_card_no(card.card_no)] = card
    return out


# ==========================================================================
# Hybrid entry point
# ==========================================================================
def get_live_cards(force_refresh: bool = False) -> Tuple[List[LiveCard], str]:
    """
    Return (cards, source_label). source_label is one of:
        'assets'  — loaded from Assets/LiveCardTable.json (primary)
        'web'     — scraped from llocg-th.vercel.app (force_refresh=True)
        'snapshot'— loaded from data/live_cards.json (fallback)
        'empty'   — all sources failed

    Priority: Assets → (web if force_refresh) → snapshot
    """
    # 1. Assets — primary source (ข้อมูลครบ, Score+ ถูกต้อง)
    cards = load_from_assets_live()
    if cards:
        return cards, "assets"

    # 2. Web refresh (เฉพาะเมื่อขอ)
    if force_refresh:
        try:
            cards = fetch_live_cards_from_web()
            if cards:
                return cards, "web"
        except Exception:  # noqa: BLE001
            pass

    # 3. Snapshot fallback
    cards = load_snapshot()
    if cards:
        return cards, "snapshot"
    return [], "empty"


def _build_assets_index(cards: List[DeckCard]) -> Dict[str, DeckCard]:
    """
    สร้าง card index จาก Assets cards พร้อม alias หลาย key ต่อการ์ดหนึ่งใบ

    decklog ส่ง card_no แบบ 'PL!SP-bp1-005-R' (rarity = R)
    แต่ Assets เก็บ full = 'PL!SP-bp1-005-P' (rarity = P)
    Number (base) = 'PL!SP-bp1-005' (ไม่มี rarity)

    วิธี: register ทั้ง full card_no และ base Number → decklog strip rarity แล้ว lookup เจอ
    """
    idx: Dict[str, DeckCard] = {}
    for card in cards:
        # full card_no จาก CardSubInfo (เช่น PL!SP-bp1-005-P)
        if card.card_no not in idx:
            idx[card.card_no] = card
        # base Number ไม่มี rarity (เช่น PL!SP-bp1-005) — decklog strip แล้วเจอ
        base = strip_rarity_suffix(card.card_no)
        if base and base not in idx:
            idx[base] = card
    return idx


def get_card_index(force_refresh: bool = False) -> Tuple[Dict[str, DeckCard], str]:
    """
    Return (index, source_label) — index keyed by card_no.

    Priority: Assets → (web if force_refresh) → snapshot
    """
    # 1. Assets — Member + Live ครบทุกใบ (รวม alias key สำหรับ decklog card_no format)
    cards = load_from_assets_members()
    if cards:
        return _build_assets_index(cards), "assets"

    # 2. Web refresh
    if force_refresh:
        try:
            cards = fetch_card_index_from_web()
            if cards:
                return {c.card_no: c for c in cards}, "web"
        except Exception:  # noqa: BLE001
            pass

    # 3. Snapshot fallback
    index = load_card_index()
    if index:
        return index, "snapshot"
    return {}, "empty"
