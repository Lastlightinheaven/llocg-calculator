"""Verify our math reproduces the Google Sheet's 90.85% example."""
import sys
sys.path.insert(0, "/home/claude/lovelive_calculator")

from models import (
    Color, DeckComposition, WaitingRoom, LiveRequirement,
    StageMembers, GameState,
)
from probability import calculate_live_success_probability, simple_target_probability


def test_google_sheet_example():
    """
    From the user's sheet:
      Deck: Red=26, Purple=5, Yellow=14, All=8, Non-Trigger=7  (total 60)
      Already out: Red=15, All=3, Non-Trigger=4, + some Purple/Yellow
                   (total 35 cards out, 25 remaining)
      Draw 10 cards, need 5+ Red (target), max 2 Non-Trigger
      Expected: 90.85%
    """
    # Remaining deck = 25 cards with this breakdown:
    # Red=11, All=5, Non=3, Purple+Yellow=6
    # For the simple_target_probability test:
    remaining = DeckComposition(
        trigger_counts={
            Color.RED: 11,
            Color.PURPLE: 2,   # arbitrary split; only target vs. non-target matters
            Color.YELLOW: 4,
        },
        all_trigger=5,
        non_trigger=3,
    )
    result = simple_target_probability(
        remaining_deck=remaining,
        target_color=Color.RED,
        draws=10,
        target_needed=5,
        non_trigger_max=2,
    )
    print(f"Simple target calc: {result.percent():.2f}%")
    print(f"  favorable = {result.favorable_cases}, total = {result.total_cases}")
    assert abs(result.percent() - 90.85) < 0.01, f"Expected 90.85%, got {result.percent():.2f}%"
    print("✅ simple_target_probability matches Google Sheet (90.85%)")


def test_full_game_state():
    """
    Replicate the same scenario using the full GameState model
    with a multivariate hypergeometric enumeration.
    """
    # Full deck (initial)
    deck = DeckComposition(
        trigger_counts={
            Color.RED: 26,
            Color.PURPLE: 5,
            Color.YELLOW: 14,
        },
        all_trigger=8,
        non_trigger=7,
    )
    assert deck.total() == 60, f"Deck total = {deck.total()}"

    # Cards already out of deck (35 cards)
    # Red out = 15, All out = 3, Non out = 4, Others out = 13
    # Let's distribute 13 as Purple=3, Yellow=10 (just an example)
    waiting = WaitingRoom(
        trigger_counts={
            Color.RED: 15,
            Color.PURPLE: 3,
            Color.YELLOW: 10,
        },
        all_trigger=3,
        non_trigger=4,
    )
    assert waiting.total() == 35

    # Live requiring say: Red=5 and some gray
    # To match the "need 5 Red from Yell and max 2 Non-Trigger", the requirement
    # post-subtracting basic hearts should yield: Red=5, Gray=3 from Yell (10-5-2=3)
    # But wait — sheet's formula: non_trigger_max = draws - (target_needed + other_needed)
    # 10 - 5 - 3 = 2, so we need 3 more hearts "of any type". That's Gray=3 in Live.
    # Or: total required = 8, of which 5 Red, 3 Gray, and basic hearts = 0.
    live = LiveRequirement(
        name="Test Live",
        required_hearts={Color.RED: 5, Color.GRAY: 3},
    )

    # No basic hearts on stage, all 10 blades
    stage = StageMembers(basic_hearts={}, blade_count=10)

    state = GameState(
        deck=deck,
        waiting_room=waiting,
        stage=stage,
        lives=[live],
    )

    remaining = state.remaining_deck()
    print(f"Remaining deck: Red={remaining.count(Color.RED)}, "
          f"Purple={remaining.count(Color.PURPLE)}, "
          f"Yellow={remaining.count(Color.YELLOW)}, "
          f"All={remaining.all_trigger}, Non={remaining.non_trigger}, "
          f"total={remaining.total()}")

    result = calculate_live_success_probability(state)
    print(f"Full game state calc: {result.percent():.2f}%")
    print(f"  favorable = {result.favorable_cases}, total = {result.total_cases}")
    assert abs(result.percent() - 90.85) < 0.01, f"Expected 90.85%, got {result.percent():.2f}%"
    print("✅ Full GameState calculation also matches 90.85%")


def test_parse_required_heart():
    """parse_required_heart ต้องแปลง string จาก Thai DB ให้ตรงกับ Color enum ของเรา."""
    from card_db import parse_required_heart

    assert parse_required_heart("red:5,grey:3") == {Color.RED: 5, Color.GRAY: 3}
    assert parse_required_heart("grey:4") == {Color.GRAY: 4}
    assert parse_required_heart("") == {}
    assert parse_required_heart("   ") == {}
    # grey (UK) and gray (US) both map to GRAY
    assert parse_required_heart("gray:2") == {Color.GRAY: 2}
    # whitespace tolerance
    assert parse_required_heart("blue:1, purple:1 , grey:3") == {
        Color.BLUE: 1, Color.PURPLE: 1, Color.GRAY: 3
    }
    # unknown colors are skipped silently
    assert parse_required_heart("orange:2,red:1") == {Color.RED: 1}
    # malformed pairs are skipped (zero counts dropped)
    assert parse_required_heart("red:0,blue:abc,green:2") == {Color.GREEN: 2}
    print("✅ parse_required_heart covers happy path + malformed input")


def test_snapshot_roundtrip():
    """LiveCard.to_json() / from_json() ต้อง roundtrip ได้ตรง."""
    from card_db import LiveCard

    c = LiveCard(
        name="Test Live",
        card_no="TEST-001-L",
        required_hearts={Color.RED: 5, Color.GRAY: 3},
        score=4,
        special_heart="Score+1",
        series="Test Series",
        product="Test Pack",
        image="https://example/img.png",
    )
    restored = LiveCard.from_json(c.to_json())
    assert restored == c, f"Roundtrip mismatch: {c} != {restored}"
    print("✅ LiveCard JSON roundtrip preserves all fields")


def test_snapshot_to_requirement():
    """LiveCard ที่ load จาก snapshot จริงต้องแปลงเป็น LiveRequirement ใช้ได้."""
    from card_db import load_snapshot

    cards = load_snapshot()
    if not cards:
        print("⚠️  snapshot ว่าง — ข้าม test (รัน `python build_card_snapshot.py` ก่อน)")
        return
    # every loaded card should convert to a valid LiveRequirement
    for c in cards:
        req = c.to_requirement()
        assert req.name == c.name
        assert req.total_required() == sum(c.required_hearts.values())
    # and at least one of them should have non-trivial hearts
    non_trivial = [c for c in cards if c.required_hearts]
    assert non_trivial, "ไม่พบการ์ดใดที่มี required_hearts ใน snapshot"
    print(f"✅ Snapshot OK — {len(cards)} cards load & convert correctly "
          f"({len(non_trivial)} มี required hearts)")


def test_parse_blade_heart():
    """blade_heart ควรแปลงเป็น Optional[Color]: "" → None, "all" → ALL, สี → enum ตรง."""
    from card_db import parse_blade_heart

    assert parse_blade_heart("") is None
    assert parse_blade_heart("   ") is None
    assert parse_blade_heart("red") == Color.RED
    assert parse_blade_heart("BLUE") == Color.BLUE   # case-insensitive
    assert parse_blade_heart("all") == Color.ALL
    assert parse_blade_heart("grey") == Color.GRAY
    assert parse_blade_heart("gray") == Color.GRAY
    assert parse_blade_heart("rainbow") is None      # unknown → None (Non-Trigger)
    print("✅ parse_blade_heart maps trigger color strings correctly")


def test_parse_pasted_deck_list():
    """parse_pasted_deck_list ต้องรองรับหลาย format และรวม duplicate."""
    from deck_import import parse_pasted_deck_list

    text = """
    # comment line — ข้าม
    3 LL-bp1-001-R+
    4x LL-bp1-002-R
    LL-bp1-003-L x2
    LL-bp1-004-N, 3
    LL-bp1-005-C
    2 LL-bp1-001-R+
    """
    entries = parse_pasted_deck_list(text)
    by_no = {e.card_no: e.count for e in entries}
    # duplicate LL-bp1-001-R+ → 3+2 = 5
    assert by_no.get("LL-bp1-001-R+") == 5, by_no
    assert by_no.get("LL-bp1-002-R") == 4
    assert by_no.get("LL-bp1-003-L") == 2
    assert by_no.get("LL-bp1-004-N") == 3
    assert by_no.get("LL-bp1-005-C") == 1
    assert parse_pasted_deck_list("") == []
    assert parse_pasted_deck_list("# only comments\n// nothing here") == []
    print("✅ parse_pasted_deck_list handles multiple formats + dedup")


def test_decklog_payload_parser():
    """_entries_from_decklog_payload ต้องดึงเฉพาะ main 'list' (type=1), ข้าม 'sub_list' (Energy)."""
    from deck_import import _entries_from_decklog_payload

    sample = {
        "id": 1, "deck_id": "TEST1", "title": "T", "game_title_id": 109,
        "list": [
            {"card_number": "C1", "num": 4, "type": 1, "card_kind": "M"},
            {"card_number": "C2", "num": 3, "type": 1, "card_kind": "L"},
        ],
        "sub_list": [
            {"card_number": "E1", "num": 12, "type": 2, "card_kind": "E"},
        ],
    }
    entries = _entries_from_decklog_payload(sample)
    by_no = {e.card_no: e.count for e in entries}
    assert by_no == {"C1": 4, "C2": 3}, by_no

    # Empty / malformed payloads
    assert _entries_from_decklog_payload({}) == []
    assert _entries_from_decklog_payload({"list": None}) == []
    assert _entries_from_decklog_payload([]) == []
    print("✅ _entries_from_decklog_payload skips sub_list (Energy) correctly")


def test_compose_deck_from_entries():
    """compose_deck_from_entries ต้องกระจายการ์ดเข้า bucket ตาม trigger_color."""
    from card_db import DeckCard
    from deck_import import DeckEntry, compose_deck_from_entries

    # Synthetic card index: 1 red Member, 1 all-trigger Live, 1 Non-Trigger Energy
    idx = {
        "C1": DeckCard(name="M1", card_no="C1", card_type="member",
                       trigger_color=Color.RED),
        "C2": DeckCard(name="L1", card_no="C2", card_type="live",
                       trigger_color=Color.ALL),
        "C3": DeckCard(name="E1", card_no="C3", card_type="energy",
                       trigger_color=None),
    }
    entries = [
        DeckEntry("C1", 20),
        DeckEntry("C2", 10),
        DeckEntry("C3", 25),
        DeckEntry("UNKNOWN", 5),
    ]
    dc, warnings = compose_deck_from_entries(entries, idx)

    assert dc.trigger_counts[Color.RED] == 20
    assert dc.trigger_counts[Color.BLUE] == 0
    assert dc.all_trigger == 10
    assert dc.non_trigger == 25
    assert dc.total() == 55
    # warnings: unknown card + total != 60
    assert any("UNKNOWN" in w for w in warnings), warnings
    assert any("60" in w for w in warnings), warnings

    # perfect deck → no total warning
    entries2 = [DeckEntry("C1", 25), DeckEntry("C2", 10), DeckEntry("C3", 25)]
    dc2, warn2 = compose_deck_from_entries(entries2, idx)
    assert dc2.total() == 60
    assert not warn2, warn2
    print("✅ compose_deck_from_entries bucketizes correctly + emits warnings")


def test_card_index_snapshot():
    """card index snapshot ต้องโหลดได้, มีการ์ดทุกประเภท และมี trigger color หลากหลาย."""
    from card_db import load_card_index

    idx = load_card_index()
    if not idx:
        print("⚠️  card index snapshot ว่าง — ข้าม test")
        return
    types = {c.card_type for c in idx.values()}
    assert "member" in types, f"expected member in snapshot, got {types}"
    assert "live" in types
    # อย่างน้อยต้องมีการ์ดที่มี trigger_color จริงๆ ไม่ใช่ None ทั้งหมด
    triggered = [c for c in idx.values() if c.trigger_color is not None]
    assert len(triggered) > 100, f"expected many triggered cards, got {len(triggered)}"
    print(f"✅ card index snapshot OK — {len(idx)} cards, types={sorted(types)}, "
          f"{len(triggered)} with trigger")


if __name__ == "__main__":
    test_google_sheet_example()
    print()
    test_full_game_state()
    print()
    test_parse_required_heart()
    test_snapshot_roundtrip()
    test_snapshot_to_requirement()
    test_parse_blade_heart()
    test_parse_pasted_deck_list()
    test_decklog_payload_parser()
    test_compose_deck_from_entries()
    test_card_index_snapshot()
    print("\n🎉 All tests passed!")
