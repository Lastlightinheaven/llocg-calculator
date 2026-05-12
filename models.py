"""
Data models for Love Live Official Card Game probability calculator.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Color(str, Enum):
    """Heart / Trigger colors in the game."""
    RED = "red"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"
    PURPLE = "purple"
    PINK = "pink"
    GRAY = "gray"  # Gray = wildcard requirement (any color can fill)
    ALL = "all"    # All Trigger = wildcard reward (fills any color)

    @classmethod
    def heart_colors(cls) -> List["Color"]:
        """Colors that appear as required hearts on Live cards (excluding ALL which is wildcard reward)."""
        return [cls.RED, cls.BLUE, cls.GREEN, cls.YELLOW, cls.PURPLE, cls.PINK, cls.GRAY]

    @classmethod
    def trigger_colors(cls) -> List["Color"]:
        """Colors that appear as triggers in deck (excluding GRAY which is requirement-only)."""
        return [cls.RED, cls.BLUE, cls.GREEN, cls.YELLOW, cls.PURPLE, cls.PINK]


# Thai labels for UI display
COLOR_LABELS_TH: Dict[Color, str] = {
    Color.RED:    "แดง",
    Color.BLUE:   "ฟ้า",
    Color.GREEN:  "เขียว",
    Color.YELLOW: "เหลือง",
    Color.PURPLE: "ม่วง",
    Color.PINK:   "ชมพู",
    Color.GRAY:   "เทา",
    Color.ALL:    "All (wildcard)",
}

# Emoji / color for visual display
COLOR_EMOJI: Dict[Color, str] = {
    Color.RED:    "🟥",
    Color.BLUE:   "🟦",
    Color.GREEN:  "🟩",
    Color.YELLOW: "🟨",
    Color.PURPLE: "🟪",
    Color.PINK:   "🩷",
    Color.GRAY:   "⬜",
    Color.ALL:    "🌈",
}


@dataclass
class DeckComposition:
    """
    The composition of a 60-card deck by trigger type.

    trigger_counts: How many cards of each trigger color are in the deck.
                    E.g. {Color.RED: 26, Color.PURPLE: 5, Color.YELLOW: 14, ...}
    all_trigger:    Number of "All Trigger" wildcard cards (counts as any color).
    non_trigger:    Number of cards with no trigger at all (won't give hearts on Yell).
    """
    trigger_counts: Dict[Color, int] = field(default_factory=dict)
    all_trigger: int = 0
    non_trigger: int = 0
    score_plus_count: int = 0  # Live cards in deck that have Score+ effect

    def total(self) -> int:
        """Total card count — should be 60 for a legal deck."""
        return sum(self.trigger_counts.values()) + self.all_trigger + self.non_trigger

    def count(self, color: Color) -> int:
        """Get count of a specific category. Color.ALL -> all_trigger."""
        if color == Color.ALL:
            return self.all_trigger
        return self.trigger_counts.get(color, 0)

    def validate(self) -> List[str]:
        """Return a list of validation errors (empty = valid)."""
        errors = []
        total = self.total()
        if total != 60:
            errors.append(f"จำนวนการ์ดรวม = {total} (ต้องเท่ากับ 60)")
        for color, n in self.trigger_counts.items():
            if n < 0:
                errors.append(f"จำนวน {color.value} เป็นลบไม่ได้")
        if self.all_trigger < 0:
            errors.append("All Trigger เป็นลบไม่ได้")
        if self.non_trigger < 0:
            errors.append("Non-Trigger เป็นลบไม่ได้")
        return errors


@dataclass
class WaitingRoom:
    """
    Cards that have already left the main deck (are in waiting room / on stage / etc).
    These reduce the effective deck for the Yell calculation.
    """
    trigger_counts: Dict[Color, int] = field(default_factory=dict)
    all_trigger: int = 0
    non_trigger: int = 0
    score_plus_count: int = 0  # Score+ Live cards that have left the deck

    def total(self) -> int:
        return sum(self.trigger_counts.values()) + self.all_trigger + self.non_trigger

    def count(self, color: Color) -> int:
        if color == Color.ALL:
            return self.all_trigger
        return self.trigger_counts.get(color, 0)


@dataclass
class LiveRequirement:
    """
    Required hearts for a single Live card.
    Example: WE WILL! requires {RED: 1, PURPLE: 1, GRAY: 1}
             Total required = 3 hearts, of which 1 must be Red, 1 must be Purple,
             and 1 can be any color (gray = wildcard requirement).
    """
    name: str = "Live"
    required_hearts: Dict[Color, int] = field(default_factory=dict)
    score: int = 0  # score value (used for tiebreakers, not for success check)

    def required_for_color(self, color: Color) -> int:
        return self.required_hearts.get(color, 0)

    def total_required(self) -> int:
        """Total hearts required across all colors (including gray)."""
        return sum(self.required_hearts.values())

    def total_required_colored(self) -> int:
        """Total hearts required, excluding gray (wildcard)."""
        return sum(n for c, n in self.required_hearts.items() if c != Color.GRAY)


@dataclass
class StageMembers:
    """
    Basic hearts already present on stage (from Members placed).
    These contribute to the Live's heart count without being drawn from deck.
    blade_count is the number of cards that will be drawn during Yell.
    """
    basic_hearts: Dict[Color, int] = field(default_factory=dict)
    blade_count: int = 0

    def hearts_for_color(self, color: Color) -> int:
        return self.basic_hearts.get(color, 0)

    def total_basic_hearts(self) -> int:
        return sum(self.basic_hearts.values())


@dataclass
class GameState:
    """
    Complete state needed to calculate Live success probability.

    waiting_room: การ์ดทั้งหมดที่ออกจาก deck (ใช้คำนวณ remaining_deck)
    reshuffle_pool: การ์ดที่จะถูก shuffle กลับเมื่อ deck หมด (WR จริงๆ ไม่รวมมือ/Stage/Board)
                   ถ้าเป็น None หมายความว่าเท่ากับ waiting_room (เช่นใน manual mode)
    """
    deck: DeckComposition
    waiting_room: WaitingRoom
    stage: StageMembers
    lives: List[LiveRequirement]  # All lives to be played this turn (1-3)
    reshuffle_pool: Optional[WaitingRoom] = None

    def remaining_deck(self) -> DeckComposition:
        """Compute the composition of cards still in the main deck."""
        _remaining_non = max(0, self.deck.non_trigger - self.waiting_room.non_trigger)
        _remaining_sp = max(0, self.deck.score_plus_count - self.waiting_room.score_plus_count)
        remaining = DeckComposition(
            trigger_counts={},
            all_trigger=max(0, self.deck.all_trigger - self.waiting_room.all_trigger),
            non_trigger=_remaining_non,
            # Score+ ไม่สามารถมากกว่า Non-trigger ที่เหลือ
            score_plus_count=min(_remaining_sp, _remaining_non),
        )
        for color in Color.trigger_colors():
            remaining.trigger_counts[color] = max(
                0,
                self.deck.count(color) - self.waiting_room.count(color),
            )
        return remaining

    def combined_requirements(self) -> Dict[Color, int]:
        """Sum required hearts across all Live cards being played."""
        combined: Dict[Color, int] = {}
        for live in self.lives:
            for color, n in live.required_hearts.items():
                combined[color] = combined.get(color, 0) + n
        return combined

    def hearts_needed_from_yell(self) -> Dict[Color, int]:
        """
        How many hearts of each color are still needed from the Yell
        (after subtracting basic hearts from members on stage).
        Gray hearts can be satisfied by any leftover trigger.
        """
        combined = self.combined_requirements()
        needed: Dict[Color, int] = {}
        for color, n in combined.items():
            if color == Color.GRAY:
                # Gray stays as gray for now — handled later as "total" constraint
                needed[color] = n
            else:
                have = self.stage.hearts_for_color(color)
                needed[color] = max(0, n - have)
        # Gray requirement is reduced by any EXCESS basic hearts
        # Excess = basic hearts of any color that exceeds that color's specific requirement
        # (including colors that have no specific requirement at all, e.g. Yellow/Purple when
        #  the Live only requires Red + Gray)
        excess_basic = 0
        for color in self.stage.basic_hearts:
            if color == Color.GRAY:
                continue
            basic = self.stage.hearts_for_color(color)
            required_for_color = combined.get(color, 0)  # 0 if Live has no requirement for this color
            if basic > required_for_color:
                excess_basic += (basic - required_for_color)
        # Apply excess to gray
        gray_need = needed.get(Color.GRAY, 0)
        gray_need = max(0, gray_need - excess_basic)
        if Color.GRAY in needed:
            needed[Color.GRAY] = gray_need
        return needed
