"""
Decklog Publish — สร้าง deck ใหม่บน decklog-en.bushiroad.com จาก server side โดยตรง

Flow (reverse-engineered จาก Vue app):
  1. POST /system/app-ja/api/create/  → ได้ {token_id, token, cur_deck_count}
  2. POST /system/app-ja/api/publish/109  พร้อม {no:[card_number...], num:[count...], token_id, token, ...}
  → ได้ {status:"OK", deck_id:"XXXXX"}

Usage:
  result = publish_deck_to_decklog(entries, title="My Deck")
  # result.deck_id  เช่น "6GKR5"
  # result.url      เช่น "https://decklog-en.bushiroad.com/ja/view/6GKR5"
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
from dataclasses import dataclass
from typing import List


DECKLOG_BASE = "https://decklog-en.bushiroad.com"
GAME_TITLE_ID = 109  # LLOCG
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class DecklogPublishError(RuntimeError):
    """ส่ง deck ไป Decklog ไม่สำเร็จ"""


@dataclass
class PublishResult:
    deck_id: str
    url: str


def publish_deck_to_decklog(
    entries: List[dict],
    title: str = "My Deck",
    timeout: float = 30.0,
    attempts: int = 3,
) -> PublishResult:
    """
    สร้าง deck ใหม่บน Decklog และคืน PublishResult พร้อม deck_id และ URL

    Parameters
    ----------
    entries : List[dict]
        List ของ {"card_no": str, "count": int}  — เหมือน editor_entries
    title   : str
        ชื่อ deck บน Decklog
    timeout : float
        Network timeout ต่อ request

    Returns
    -------
    PublishResult

    Raises
    ------
    DecklogPublishError  ถ้า network หรือ Decklog ตอบ NG
    """
    if not entries:
        raise DecklogPublishError("Deck ว่างเปล่า")

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    headers = {
        "User-Agent": _UA,
        "Accept": "application/json, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{DECKLOG_BASE}/ja/create?c={GAME_TITLE_ID}",
        "Origin": DECKLOG_BASE,
        "Content-Type": "application/json;charset=UTF-8",
    }

    def _is_timeout(err: BaseException) -> bool:
        if isinstance(err, (TimeoutError, socket.timeout)):
            return True
        reason = getattr(err, "reason", None)
        return isinstance(reason, (TimeoutError, socket.timeout))

    def _post(url: str, payload: object, what: str) -> object:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_err: BaseException | None = None
        for i in range(max(1, attempts)):
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with opener.open(req, timeout=timeout) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body) if body.strip() else {}
            except urllib.error.HTTPError as e:
                raise DecklogPublishError(f"HTTP {e.code} ตอน{what}: {e.url}") from e
            except urllib.error.URLError as e:
                last_err = e
                if not _is_timeout(e):
                    raise DecklogPublishError(f"เชื่อมต่อ Decklog ไม่ได้ ({what}): {e.reason}") from e
            except (TimeoutError, socket.timeout) as e:
                last_err = e
            except Exception as e:
                raise DecklogPublishError(f"Network error ({what}): {e}") from e
            # timeout → รอสั้นๆ แล้วลองใหม่
            if i < attempts - 1:
                time.sleep(1.5)
        raise DecklogPublishError(
            f"หมดเวลาเชื่อมต่อ Decklog ตอน{what} (timeout {timeout:.0f}s × {attempts} ครั้ง) — "
            f"เซิร์ฟเวอร์ Decklog อาจช้าหรือไม่ตอบสนอง ลองใหม่อีกครั้งภายหลัง"
        ) from last_err

    # Step 0: warm-up — โหลดหน้า create ให้ cookie/session พร้อมเหมือน browser (best-effort)
    try:
        warm = urllib.request.Request(
            f"{DECKLOG_BASE}/ja/create?c={GAME_TITLE_ID}", headers={"User-Agent": _UA}
        )
        with opener.open(warm, timeout=timeout) as r:
            r.read()
    except Exception:
        pass  # ไม่เป็นไร ขั้นตอนหลักจัดการ error เอง

    # Step 1: Get CSRF token
    token_data = _post(f"{DECKLOG_BASE}/system/app-ja/api/create/", {}, "ขอ token")
    if not isinstance(token_data, dict) or "token_id" not in token_data:
        raise DecklogPublishError(f"ไม่ได้รับ token จาก Decklog: {token_data}")

    token_id = token_data["token_id"]
    token = token_data["token"]

    # Step 2: Build no/num arrays (card_number string, count)
    no_arr: List[str] = []
    num_arr: List[int] = []
    for e in entries:
        no_arr.append(str(e["card_no"]))
        num_arr.append(int(e["count"]))

    payload = {
        "id": "",
        "deck_id": "",
        "title": title or "My Deck",
        "memo": "",
        "deck_param1": "",
        "deck_param2": "",
        "add_param1": "",
        "add_param2": "",
        "no": no_arr,
        "num": num_arr,
        "sub_no": [],
        "sub_num": [],
        "p_no": [],
        "p_num": [],
        "p_slot": [],
        "g_no": [],
        "has_session": False,
        "token_id": token_id,
        "token": token,
    }

    # Step 3: Publish
    result = _post(f"{DECKLOG_BASE}/system/app-ja/api/publish/{GAME_TITLE_ID}", payload, "ส่ง deck")

    if not isinstance(result, dict):
        raise DecklogPublishError(f"Decklog ตอบกลับผิดรูปแบบ: {result}")

    status = result.get("status", "")
    if status == "TOKEN-NG":
        raise DecklogPublishError("Token หมดอายุ กรุณาลองใหม่อีกครั้ง")
    if status != "OK":
        raise DecklogPublishError(f"Decklog ปฏิเสธ deck (status={status})")

    deck_id = result.get("deck_id") or result.get("id") or ""
    if not deck_id:
        raise DecklogPublishError("Decklog ไม่ส่ง deck_id กลับมา")

    return PublishResult(
        deck_id=str(deck_id),
        url=f"{DECKLOG_BASE}/ja/view/{deck_id}",
    )
