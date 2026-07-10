"""
Icon helper — แปลง PNG ใน Assets/Icon/ เป็น <img> (base64 data URI) สำหรับฝังใน HTML
(st.markdown unsafe_allow_html). ใช้แทน emoji: blade / blade heart แต่ละสี / draw / score+ / energy.

หมายเหตุ: ใช้ได้เฉพาะที่ render ผ่าน st.markdown(HTML) — widget label/caption ที่ไม่ render HTML
ยังต้องใช้ emoji เดิม.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from models import Color

_ICON_DIR = Path(__file__).parent / "Assets" / "Icon"

# Color (blade heart / trigger) → ชื่อไฟล์ icon
_BLADEHEART_FILE = {
    Color.RED: "bladeheart_red",
    Color.BLUE: "bladeheart_blue",
    Color.GREEN: "bladeheart_green",
    Color.YELLOW: "bladeheart_yellow",
    Color.PURPLE: "bladeheart_purple",
    Color.PINK: "bladeheart_pink",
    Color.ALL: "bladeheart_all",
}


@lru_cache(maxsize=None)
def _data_uri(name: str) -> str:
    p = _ICON_DIR / f"{name}.png"
    if not p.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def icon_img(name: str, size: str = "1.1em") -> str:
    """คืน <img> HTML ของ icon (ว่างถ้าไม่พบไฟล์)."""
    uri = _data_uri(name)
    if not uri:
        return ""
    return (f'<img src="{uri}" style="height:{size};width:auto;'
            f'vertical-align:-0.18em;display:inline-block;" alt="">')


def blade(size: str = "1.1em") -> str:
    return icon_img("blade", size)


def energy(size: str = "1.1em") -> str:
    return icon_img("energy", size)


def draw(size: str = "1.1em") -> str:
    return icon_img("draw_1", size)


def score(size: str = "1.1em") -> str:
    return icon_img("score_1", size)


def bladeheart(color, size: str = "1.1em") -> str:
    """icon blade heart ตามสี (None → bladeheart_none)."""
    return icon_img(_BLADEHEART_FILE.get(color, "bladeheart_none"), size)


def bladeheart_none(size: str = "1.1em") -> str:
    return icon_img("bladeheart_none", size)


def has_icons() -> bool:
    """มีไฟล์ icon ครบพอใช้ไหม (fallback เป็น emoji ถ้าไม่มี)."""
    return bool(_data_uri("blade"))
