"""
Live card database — Assets-first.

Strategy (ลำดับความสำคัญ):
  1. Assets/LiveCardTable.json + Assets/MemberCardTable.json = primary source
     (ข้อมูลครบถ้วน, Score+ ถูกต้อง, รูปการ์ด local)
  2. bundled snapshot data/live_cards.json = fallback ถ้าไม่มี Assets
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from models import Color, LiveRequirement


SNAPSHOT_PATH = Path(__file__).parent / "data" / "live_cards.json"
CARD_INDEX_PATH = Path(__file__).parent / "data" / "cards_index.json"

ASSETS_DIR = Path(__file__).parent / "Assets"
ASSETS_LIVE_JSON = ASSETS_DIR / "LiveCardTable.json"
ASSETS_MEMBER_JSON = ASSETS_DIR / "MemberCardTable.json"
ASSETS_CARD_TEXT_TH = ASSETS_DIR / "CardTextTH.json"
ASSETS_CARD_TEXT_FIX = ASSETS_DIR / "CardTextFix.json"
ASSETS_NAME_MAPPING = ASSETS_DIR / "Name mapping.json"
ASSETS_LOVE_POINTS = ASSETS_DIR / "LoveKaPoints.json"
ASSETS_KEYWORD_MAP = ASSETS_DIR / "keyword_map.json"
ASSETS_CARD_LIST_DIR = ASSETS_DIR / "Card List"
ASSETS_IMAGES_LIVE = ASSETS_DIR / "Images" / "Live"
ASSETS_IMAGES_MEMBER = ASSETS_DIR / "Images" / "Member"


def _load_name_mapping() -> Dict[str, str]:
    """โหลด {Japanese Name: English Name} จาก Assets/Name mapping.json"""
    if not ASSETS_NAME_MAPPING.exists():
        return {}
    data = json.loads(ASSETS_NAME_MAPPING.read_text(encoding="utf-8"))
    mapping = {entry["Japanese Name"]: entry["English Name"] for entry in data if "Japanese Name" in entry and "English Name" in entry}
    # Katakana variant สำหรับการ์ดที่ใช้ spelling ต่างจาก mapping
    mapping.setdefault("統堂エレナ", "Toudou Erena")
    return mapping


_NAME_MAP: Optional[Dict[str, str]] = None


def _translate_name(jp_name: str) -> str:
    """แปลงชื่อภาษาญี่ปุ่นเป็นภาษาอังกฤษ ถ้าไม่มี mapping คืน original
    รองรับชื่อ multi-member ที่คั่นด้วย & โดยแปลงทีละส่วน
    """
    global _NAME_MAP
    if _NAME_MAP is None:
        _NAME_MAP = _load_name_mapping()
        # index ที่ normalize whitespace เพื่อ match กรณี DB กับ mapping มี space ต่างกัน
        _NAME_MAP.update({k.replace(" ", "").replace("　", ""): v for k, v in list(_NAME_MAP.items())})

    def _lookup(name: str) -> str:
        return _NAME_MAP.get(name) or _NAME_MAP.get(name.replace(" ", "").replace("　", ""), name)

    if "&" in jp_name:
        parts = [_lookup(p.strip()) for p in jp_name.split("&")]
        return " & ".join(parts)
    return _lookup(jp_name)

_CARD_IMAGE_BASE = "https://llofficial-cardgame.com/wordpress/wp-content/images/cardlist"

# Normalize card_no ให้ตรงกันทั้ง DB และ decklog:
#   - full-width plus (＋ U+FF0B) → ASCII +
#   - space ก่อน + หรือ ＋ (decklog ส่ง "R +" แต่ DB เก็บ "R＋") → ลบ space
def normalize_card_no(card_no: str) -> str:
    return card_no.replace(" ＋", "＋").replace("＋", "+").replace(" +", "+")


_JP_CHARS = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")


def display_names(name: str, name_alt: str = "") -> Tuple[str, str]:
    """
    คืน (english_primary, japanese_secondary) — จัดให้ 'อังกฤษเป็นหลักเสมอ'.
    Member: name=EN, name_alt=JP → (EN, JP). Song: name=JP, name_alt=EN → สลับเป็น (EN, JP).
    ถ้าไม่มี name_alt คืน (name, "").
    """
    if name_alt and _JP_CHARS.search(name or "") and not _JP_CHARS.search(name_alt):
        return name_alt, name          # name เป็นญี่ปุ่น (เพลง) → เอา alt (อังกฤษ) ขึ้นก่อน
    return name, name_alt


# Cache: card_no (normalized) → image URL, loaded from Assets/Card List CSVs
_card_list_image_map: Optional[Dict[str, str]] = None


def _load_card_list_image_map() -> Dict[str, str]:
    """Build {normalized_card_no: image_url} from all CSVs in Assets/Card List/."""
    global _card_list_image_map
    if _card_list_image_map is not None:
        return _card_list_image_map
    result: Dict[str, str] = {}
    if not ASSETS_CARD_LIST_DIR.exists():
        _card_list_image_map = result
        return result
    import csv
    for csv_path in ASSETS_CARD_LIST_DIR.glob("*.csv"):
        try:
            with csv_path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    card_no = normalize_card_no((row.get("card_no") or "").strip())
                    image = (row.get("image") or "").strip()
                    if card_no and image:
                        result[card_no] = image
        except Exception:
            continue
    _card_list_image_map = result
    return result


def card_no_to_image_url(card_no: str) -> str:
    """คืน URL รูปการ์ดจาก Assets/Card List CSVs (ข้อมูลจากเว็บ Official โดยตรง)."""
    cn = normalize_card_no(card_no)
    img_map = _load_card_list_image_map()
    return img_map.get(cn, "")


# Cache: base card_no → [(full_card_no, image_url)] ทุก rarity (เรียงตามลำดับใน CSV)
_card_rarity_images: Optional[Dict[str, List[Tuple[str, str]]]] = None


def card_images_by_rarity(card_no: str) -> List[Tuple[str, str]]:
    """
    คืนรูปการ์ดทุก rarity ของ base เดียวกัน เป็น [(full_card_no, image_url), ...].

    เช่น card_no = "PL!N-bp1-002-P" → คืนรูปของ -P, -P+, -R+, -SEC ทั้งหมด
    (base card เดียวกันแต่คนละ rarity ใช้รูปคนละใบ). ใช้ base card_no (ไม่มี rarity)
    เป็น key — dedup รูปซ้ำ, คงลำดับที่เจอใน CSV.
    """
    global _card_rarity_images
    if _card_rarity_images is None:
        idx: Dict[str, List[Tuple[str, str]]] = {}
        seen: Dict[str, set] = {}
        for full_cn, img in _load_card_list_image_map().items():
            base = strip_rarity_suffix(full_cn)
            if base not in idx:
                idx[base] = []
                seen[base] = set()
            if img not in seen[base]:
                idx[base].append((full_cn, img))
                seen[base].add(img)
        _card_rarity_images = idx

    base = strip_rarity_suffix(normalize_card_no(card_no))
    return list(_card_rarity_images.get(base, []))


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

# ข้อมูล heart เก็บสีเป็น "grey", models.py ใช้ Color.GRAY — แมพตรงๆ
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
    unit: str = ""
    cost: int = 0
    image: str = ""
    text_th: str = ""                    # card effect text (Thai) จาก Assets/CardTextTH.json
    name_alt: str = ""                   # ชื่ออีกภาษา (เช่น อังกฤษ) จาก Assets/CardNameMap.json

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "card_no": self.card_no,
            "card_type": self.card_type,
            "trigger_color": self.trigger_color.value if self.trigger_color else None,
            "blade": self.blade,
            "base_heart": {c.value: n for c, n in self.base_heart.items()},
            "series": self.series,
            "unit": self.unit,
            "cost": self.cost,
            "image": self.image,
            "text_th": self.text_th,
            "name_alt": self.name_alt,
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
            unit=d.get("unit", "") or "",
            cost=int(d.get("cost") or 0),
            image=d.get("image", "") or "",
            text_th=d.get("text_th", "") or "",
            name_alt=d.get("name_alt", "") or "",
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
    name_alt: str = ""                   # ชื่ออีกภาษา (เช่น อังกฤษ) จาก Assets/CardNameMap.json

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
            "name_alt": self.name_alt,
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
            name_alt=d.get("name_alt", "") or "",
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
      'スコア' / 'score'  → ค้นหา 'Score +N' ใน text_card; ไม่เจอ → 1
                          (bare score token = มี Score+ trigger, JSON เก็บเป็น score:1)
    """
    s = (special_heart or "").strip()
    # format ตรงๆ เช่น 'Score+1'
    m = re.match(r"Score\+(\d+)", s, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # format ภาษาญี่ปุ่น/lowercase → มี Score+ trigger
    if s in ("スコア", "score"):
        text = text_card if isinstance(text_card, str) else " ".join(text_card)
        m2 = re.search(r"Score\s*\+\s*(\d+)", text, re.IGNORECASE)
        return int(m2.group(1)) if m2 else 1
    return 0


def _coerce_int(v) -> int:
    """DB เก็บ score เป็น int, str, หรือ ว่าง — ทำให้เป็น int เสมอ.
    รองรับ float string จาก CSV (เช่น '9.0' → 9)."""
    if v is None or v == "":
        return 0
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if not s:
        return 0
    try:
        return int(s)
    except (ValueError, TypeError):
        pass
    try:
        return int(float(s))
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
    """คืน URL รูปการ์ดจาก Assets/Card List CSVs โดยใช้ filename จาก CardSubInfo."""
    bare = Path(filename).name
    card_no = bare.replace(".png", "").replace(".PNG", "")
    return card_no_to_image_url(card_no)


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

        img_path = card_no_to_image_url(card_no_full)

        required: Dict[Color, int] = {}
        for field_name, color in _ASSETS_HEART_FIELDS.items():
            n = _coerce_int(obj.get(field_name, 0))
            if n > 0:
                required[color] = n

        _bh = obj.get("BladeHeart", "") or ""
        _trigger_color, score_plus = _parse_assets_bladeheart(_bh)

        _live_name = obj.get("Name", "") or ""
        _live_alt = _translate_name(_live_name)   # ชื่ออังกฤษจาก Name mapping.json (ถ้ามี)
        cards.append(LiveCard(
            name=_live_name,
            card_no=card_no_full,
            required_hearts=required,
            score=_coerce_int(obj.get("Score", 0)),
            score_plus=score_plus,
            special_heart=_bh,
            series=obj.get("Group", "") or "",
            product=obj.get("Contain", "") or "",
            image=img_path,
            name_alt=(_live_alt if _live_alt and _live_alt != _live_name else ""),
        ))
    return cards


# ---------------------------------------------------------------------------
# Card List CSV loader (เฟส 1 — ขนานกับ JSON, ยังไม่สลับ priority)
# ---------------------------------------------------------------------------

# CSV เก็บ series เป็นชื่อเต็มญี่ปุ่น แต่ DB/UI ใช้ชื่อวง (Group) — แมพให้ตรง JSON เดิม
_CSV_SERIES_TO_GROUP: Dict[str, str] = {
    "ラブライブ！": "μ's",
    "ラブライブ！サンシャイン!!": "Aqours",
    "ラブライブ！虹ヶ咲学園スクールアイドル同好会": "虹ヶ咲",
    "ラブライブ！スーパースター!!": "Liella!",
    "蓮ノ空女学院スクールアイドルクラブ": "蓮ノ空",
}

# card_type ญี่ปุ่นใน CSV → tag ภายใน
_CSV_TYPE_MAP: Dict[str, str] = {
    "メンバー": "member",
    "ライブ": "live",
    "エネルギー": "energy",
}


def _csv_series_to_group(series: str) -> str:
    """แปลง series ญี่ปุ่นจาก CSV → ชื่อวง (Group). multi-series (คั่นด้วย ,) เอาตัวแรก."""
    s = (series or "").strip()
    if not s:
        return ""
    first = s.split(",")[0].strip()
    return _CSV_SERIES_TO_GROUP.get(first, first)


def _parse_csv_trigger(blade_heart: str, special_heart: str) -> Tuple[Optional[Color], int]:
    """
    แปลง blade_heart + special_heart จาก CSV → (trigger_color, score_plus).

    CSV blade_heart เก็บเป็นค่าเดี่ยว "ไม่มี colon" (ต่าง JSON ที่เป็น "green:1"):
      "green" → Color.GREEN trigger
      "all" / "[全ブレード]" → Color.ALL trigger
      "スコア" / "score" → Non-Trigger + score+ (ดึงค่าจริงทีหลังจาก text/score ไม่ได้ที่นี่)
      "" → Non-Trigger
    special_heart อาจมี "draw" (ไม่ใช่ trigger) หรือ "score" — ไม่กระทบสี.
    """
    bh = (blade_heart or "").strip().lower()
    # b_heart07 = Blade Heart แบบพิเศษ — ตอน Yell เจอ ให้หัวใจเทา 2 ดวง (ไม่ใช่ trigger สี)
    # ไม่ใช่ trigger_color → คืน None ที่นี่ (grey:2 จัดการแยกใน loader ผ่าน special_heart)
    if bh in ("b_heart07", "heart07", "b_heart7", "heart7"):
        return None, 0
    trigger: Optional[Color] = None
    score_plus = 0
    if bh in ("all", "[全ブレード]".lower()):
        trigger = Color.ALL
    elif bh in ("score", "スコア"):
        score_plus = 1  # มี score trigger — ค่าจริงมักระบุใน text แต่นับเป็น 1 อย่างน้อย
    elif bh in _ASSETS_COLOR_MAP:
        trigger = _ASSETS_COLOR_MAP[bh]
    return trigger, score_plus


def _normalize_unit(unit: str) -> str:
    """
    Normalize ชื่อ unit ให้เป็นรูปเดียว — CSV เก็บ full-width/half-width ปนกัน
    ทำให้ filter เห็นเป็นคนละ unit เช่น 'みらくらぱーく！' vs 'みらくらぱーく!'.
    แปลง full-width ! ！ / space 　 → half-width canonical.
    """
    return (unit or "").strip().replace("！", "!").replace("　", " ")


def _iter_card_list_rows():
    """yield dict ทุกแถวจากทุก CSV ใน Assets/Card List/ (encoding utf-8-sig)."""
    if not ASSETS_CARD_LIST_DIR.exists():
        return
    import csv as _csv
    for csv_path in sorted(ASSETS_CARD_LIST_DIR.glob("*.csv")):
        try:
            with csv_path.open(encoding="utf-8-sig", newline="") as f:
                for row in _csv.DictReader(f):
                    yield row
        except Exception:  # noqa: BLE001
            continue


def load_from_card_list_csv() -> Tuple[List[DeckCard], List[LiveCard]]:
    """
    โหลดการ์ดทั้งหมดจาก Assets/Card List/*.csv (ผลผลิตจาก scraper).

    คืน (deck_cards, live_cards):
      - deck_cards = Member + Live + Energy (สำหรับ card_index)
      - live_cards = เฉพาะ Live (สำหรับ live-card calculator)

    CSV columns: card_name, card_name_eng, product, card_type, series, unit,
      cost, base_heart, blade_heart, blade, rarity, card_no, required_heart,
      special_heart, score, text_card, image

    เฟส 1: ฟังก์ชันนี้ยังไม่ถูกเรียกใน get_card_index — ใช้เทียบผลกับ JSON ก่อน.
    """
    deck_cards: List[DeckCard] = []
    live_cards: List[LiveCard] = []
    seen_deck: set = set()
    seen_live: set = set()

    for row in _iter_card_list_rows():
        card_no = normalize_card_no((row.get("card_no") or "").strip())
        if not card_no:
            continue
        jp_type = (row.get("card_type") or "").strip()
        tag = _CSV_TYPE_MAP.get(jp_type)
        if tag is None:
            continue

        image = (row.get("image") or "").strip()
        name_jp = (row.get("card_name") or "").strip()
        # ชื่อ EN: Name mapping.json (curated) ชนะก่อน — คุมคุณภาพได้ + แก้ typo จาก scraper
        # (เช่น "Mia Taylor20"). ถ้า mapping ไม่มี (แปลแล้วได้ค่าเดิม) → fallback card_name_eng
        _translated = _translate_name(name_jp)
        _csv_eng = (row.get("card_name_eng") or "").strip()
        if _translated and _translated != name_jp:
            name_en = _translated               # mapping มี → ใช้ค่า curated
        else:
            name_en = _csv_eng or name_jp       # ไม่มี mapping → ใช้ค่าจาก CSV
        group = _csv_series_to_group(row.get("series", ""))

        _sh = (row.get("special_heart") or "").strip()
        _bh = (row.get("blade_heart") or "").strip()
        _text = (row.get("text_card") or "").strip()
        trigger_color, _ = _parse_csv_trigger(_bh, _sh)
        # Score+ ปกติเก็บใน special_heart ("Score+1"/"score"/"スコア") แต่บางใบเก็บใน
        # blade_heart (scraper ใส่ผิด column) — เช็คทั้งสอง
        score_plus = _parse_score_plus(_sh, _text) or _parse_score_plus(_bh, _text)
        # b_heart07 = Blade Heart พิเศษ: เมื่อ Yell เจอ ให้หัวใจเทา 2 ดวง (grey:2)
        # เก็บใน special_heart เป็น "greyblade:2" เพื่อให้ Calculator นำไปคิด heart pool
        if _bh.lower() in ("b_heart07", "heart07", "b_heart7", "heart7"):
            _sh = (_sh + ", greyblade:2").strip(", ") if _sh else "greyblade:2"

        # base_heart: member ใช้ base_heart, live ใช้ required_heart (Live ไม่มี base_heart)
        _base = parse_required_heart(row.get("base_heart", "") or "")
        if tag == "live" and not _base:
            _base = parse_required_heart(row.get("required_heart", "") or "")

        # --- DeckCard (ทุก type) ---
        if card_no not in seen_deck:
            seen_deck.add(card_no)
            deck_cards.append(DeckCard(
                name=name_en,
                card_no=card_no,
                card_type=tag,
                trigger_color=trigger_color,
                blade=_coerce_int(row.get("blade")),
                base_heart=_base,
                series=group,
                unit=_normalize_unit(row.get("unit", "")),
                cost=_coerce_int(row.get("cost")),
                image=image,
                name_alt=(name_jp if name_jp and name_jp != name_en else ""),
            ))

        # --- LiveCard (เฉพาะ live) ---
        if tag == "live" and card_no not in seen_live:
            seen_live.add(card_no)
            live_cards.append(LiveCard(
                name=name_en or name_jp,
                card_no=card_no,
                required_hearts=parse_required_heart(row.get("required_heart", "") or ""),
                score=_coerce_int(row.get("score")),
                score_plus=score_plus,
                special_heart=_sh,
                series=group,
                product=(row.get("product") or "").strip(),
                image=image,
                name_alt=(name_jp if name_jp and name_jp != name_en else ""),
            ))

    return deck_cards, live_cards


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

            img_path = card_no_to_image_url(card_no_full)

            _bh = obj.get("BladeHeart", "") or ""
            trigger_color, _sp = _parse_assets_bladeheart(_bh)

            base_heart: Dict[Color, int] = {}
            for field_name, color in _ASSETS_HEART_FIELDS.items():
                if field_name == "None":
                    continue  # base_heart ไม่มี Gray
                n = _coerce_int(obj.get(field_name, 0))
                if n > 0:
                    base_heart[color] = n

            _name_jp = obj.get("Name", "") or ""
            _name_en = _translate_name(_name_jp)
            card = DeckCard(
                name=_name_en,
                card_no=card_no_full,
                card_type=card_type,
                trigger_color=trigger_color,
                blade=_coerce_int(obj.get("Blade", 0)),
                base_heart=base_heart,
                series=obj.get("Group", "") or "",
                unit=obj.get("Unit", "") or "",
                cost=_coerce_int(obj.get("Cost", 0)),
                image=img_path,
                # เก็บชื่อญี่ปุ่นเดิมไว้ (ไม่ทิ้ง) เพื่อแสดงคู่กับอังกฤษ
                name_alt=(_name_jp if _name_jp and _name_jp != _name_en else ""),
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


# ==========================================================================
# Snapshot I/O — โหลด fallback อย่างเดียว (ไม่มี save เพราะไม่ดึงจากเว็บแล้ว)
# ==========================================================================
def load_snapshot(path: Path = SNAPSHOT_PATH) -> List[LiveCard]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [LiveCard.from_json(d) for d in data.get("cards", [])]


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
        'csv'     — loaded from Assets/Card List/*.csv (primary)
        'assets'  — loaded from Assets/LiveCardTable.json (fallback)
        'snapshot'— loaded from data/live_cards.json (fallback)
        'empty'   — all sources failed

    Priority: Card List CSV → Assets JSON → snapshot.
    (force_refresh คงไว้เพื่อ compat เฉยๆ — ไม่มี web แล้ว)
    """
    # 1. Card List CSV — DB หลัก (มี grey requirement ครบ, ข้อมูลถูกต้องกว่า JSON)
    _, csv_live = load_from_card_list_csv()
    if csv_live:
        return csv_live, "csv"

    # 2. Assets JSON — fallback
    cards = load_from_assets_live()
    if cards:
        return cards, "assets"

    # 3. Snapshot fallback
    cards = load_snapshot()
    if cards:
        return cards, "snapshot"
    return [], "empty"


def load_love_points(path: Path = ASSETS_LOVE_POINTS) -> Dict[str, int]:
    """
    โหลด Love Ka Point จาก Assets/LoveKaPoints.json → {base_card_no: points}.
    การ์ดที่ไม่อยู่ในไฟล์ = 0 แต้ม. รวมใน Deck ห้ามเกิน 9 (นับ points x จำนวนใบ).
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    raw = data.get("points", {}) if isinstance(data, dict) else {}
    out: Dict[str, int] = {}
    for k, v in raw.items():
        try:
            out[normalize_card_no(k)] = int(v)
        except (ValueError, TypeError):
            continue
    return out


LOVE_POINT_MAX = 9   # แต้มรวมใน Deck ห้ามเกิน


def load_keyword_map(path: Path = ASSETS_KEYWORD_MAP) -> Dict[str, Dict[str, str]]:
    """
    โหลด keyword display map จาก Assets/keyword_map.json
    → {canonical_keyword: {"icon": ชื่อไฟล์, "hint": ความหมาย}}.

    ใช้ตอน render text_th ใน Deck Editor — keyword ที่ไม่อยู่ในไฟล์แสดงเป็นข้อความธรรมดา.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    kw = data.get("keywords", {})
    return {k: v for k, v in kw.items() if isinstance(v, dict)}


def load_card_text_fix(path: Path = ASSETS_CARD_TEXT_FIX) -> Dict[str, str]:
    """
    โหลด overlay แก้ข้อความการ์ดที่สะกดผิด จาก Assets/CardTextFix.json → {card_no: text}.

    แยกเป็นไฟล์ overlay เพื่อให้แก้ text ทับ CardTextTH.json ได้โดยไม่ต้องแก้ไฟล์หลัก
    (CardTextFix ชนะเสมอตอน merge — ดู load_card_text_th).
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    raw: Dict[str, str] = data.get("fixes", {})
    return {normalize_card_no(k): v for k, v in raw.items() if v}


def load_card_text_th(path: Path = ASSETS_CARD_TEXT_TH) -> Dict[str, str]:
    """
    โหลด Thai card text จาก Assets/CardTextTH.json → {card_no: text_th}
    แล้ว merge overlay จาก Assets/CardTextFix.json ทับ (overlay ชนะเสมอ).

    key เป็น card_no ที่ normalize แล้ว (full rarity variant).
    """
    out: Dict[str, str] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw: Dict[str, str] = data.get("cards", {})
            out = {normalize_card_no(k): v for k, v in raw.items() if v}
        except (json.JSONDecodeError, OSError):
            out = {}
    out.update(load_card_text_fix())
    return out


def _build_assets_index(cards: List[DeckCard]) -> Dict[str, DeckCard]:
    """
    สร้าง card index จาก Assets cards พร้อม alias หลาย key ต่อการ์ดหนึ่งใบ
    และ inject text_th จาก CardTextTH.json — ใช้ base card_no (ไม่มี rarity) เป็น key
    เพราะ text เก็บที่ rarity หลัก (-P) แต่เราต้องการ fallback ทุก variant
    """
    text_map = load_card_text_th()

    # index text_map ตาม base card_no → [(full_key, text), ...] เพื่อ fallback แม่นขึ้น
    # (CardTextTH มี key ทั้งแบบ full rarity และ base ปนกัน — ต้องเลือก rarity หลัก)
    _text_by_base: Dict[str, List[Tuple[str, str]]] = {}
    for _k, _v in text_map.items():
        _text_by_base.setdefault(strip_rarity_suffix(_k), []).append((_k, _v))

    # ลำดับ rarity หลัก (ตรงกับ Deck Editor) — fallback เลือกตัวนี้ก่อน base key ดิบ
    _rar_pri = ["P", "N", "L", "SD", "SD2", "PE", "CL", "DUO", "PR",
                "PP", "RM", "R", "R+", "L+", "AR", "P+", "SEC"]
    _rar_rank = {r: i for i, r in enumerate(_rar_pri)}

    def _rar_of(key: str) -> str:
        b = strip_rarity_suffix(key)
        return key[len(b) + 1:] if key.startswith(b + "-") else ""

    def _resolve_text(card_no: str) -> str:
        # 1) full card_no ตรงตัว
        if card_no in text_map:
            return text_map[card_no]
        base = strip_rarity_suffix(card_no)
        # 2) base card_no ตรงตัวใน text_map (CardTextTH เก็บ text ที่ base key เช่น PL!SP-pb2-001)
        if base in text_map:
            return text_map[base]
        # 3) fallback: เลือก text จาก sibling ที่ rarity เป็นหลักสุด (ไม่ใช่ base key ดิบมั่วๆ)
        sibs = _text_by_base.get(base, [])
        if not sibs:
            return ""
        # เรียง: rarity หลัก (rank ต่ำ) มาก่อน, base key (ไม่มี rarity) ไปท้ายสุด
        best = min(sibs, key=lambda kv: _rar_rank.get(_rar_of(kv[0]), 998)
                   if _rar_of(kv[0]) else 999)
        return best[1]

    idx: Dict[str, DeckCard] = {}
    for card in cards:
        if not card.text_th:
            card.text_th = _resolve_text(card.card_no)
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

    Priority: Card List CSV → Assets JSON → snapshot.
    (force_refresh คงไว้เพื่อ compat เฉยๆ — ไม่มี web แล้ว)
    """
    # 1. Card List CSV — DB หลัก (ครบทุก type รวม Energy, ข้อมูลถูกต้องกว่า JSON)
    csv_cards, _ = load_from_card_list_csv()
    if csv_cards:
        return _build_assets_index(csv_cards), "csv"

    # 2. Assets JSON — fallback (Member + Live, ไม่มี Energy)
    cards = load_from_assets_members()
    if cards:
        return _build_assets_index(cards), "assets"

    # 3. Snapshot fallback
    index = load_card_index()
    if index:
        return index, "snapshot"
    return {}, "empty"
