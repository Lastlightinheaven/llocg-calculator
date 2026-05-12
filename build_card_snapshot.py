"""
CLI: rebuild the bundled Live-card snapshot from the live Thai DB.

Usage:
    python build_card_snapshot.py

ควรรันเมื่อเว็บต้นทางเพิ่มการ์ดใหม่ หรือเมื่อ in-app refresh พังเพราะ
format ของเว็บเปลี่ยน (จะได้แก้ regex ใน card_db.py แล้ว regenerate ได้)
"""
from __future__ import annotations

import sys

from card_db import (
    CARD_INDEX_PATH,
    SNAPSHOT_PATH,
    fetch_card_index_from_web,
    fetch_live_cards_from_web,
    save_card_index,
    save_snapshot,
)


def main() -> int:
    # 1) Full card index (Member + Live + Energy) — สำหรับ deck-import feature
    print("Fetching full card index from web …")
    try:
        cards = fetch_card_index_from_web()
    except Exception as e:  # noqa: BLE001
        print(f"❌ Fetch full index failed: {e}", file=sys.stderr)
        return 1
    if not cards:
        print("❌ No cards extracted.", file=sys.stderr)
        return 1
    save_card_index(cards)
    print(f"✅ Saved {len(cards)} cards (all types) to {CARD_INDEX_PATH}")

    type_counts: dict[str, int] = {}
    for c in cards:
        type_counts[c.card_type] = type_counts.get(c.card_type, 0) + 1
    print("  breakdown:", type_counts)

    # 2) Live-only snapshot (คงไว้สำหรับ UI selectbox เดิม)
    print("\nFetching Live cards snapshot …")
    try:
        live = fetch_live_cards_from_web()
    except Exception as e:  # noqa: BLE001
        print(f"❌ Fetch Live cards failed: {e}", file=sys.stderr)
        return 1
    save_snapshot(live)
    print(f"✅ Saved {len(live)} Live cards to {SNAPSHOT_PATH}")

    print("\nSample Member cards (first 3 with blade_heart):")
    shown = 0
    for c in cards:
        if c.card_type != "member" or c.trigger_color is None:
            continue
        print(f"  [{c.card_no}] {c.name}  trigger={c.trigger_color.value}")
        shown += 1
        if shown >= 3:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
