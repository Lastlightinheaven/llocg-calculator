"""
Monte Carlo simulator for Love Live OCG Live success probability.
Useful as a cross-check against the exact hypergeometric calculation,
and for handling complex edge cases.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
import random

from models import Color, GameState
from probability import _check_hearts_satisfy


@dataclass
class FailureBreakdown:
    missing_specific_color: Dict[str, int]  # color_value -> count of trials failed due to that color
    missing_total_hearts: int               # failed because total hearts < total required
    multiple_causes: int                    # failed due to more than one missing color simultaneously

    def total_fails(self) -> int:
        return sum(self.missing_specific_color.values()) + self.missing_total_hearts + self.multiple_causes


@dataclass
class SimulationResult:
    probability: float
    successes: int
    trials: int
    draws: int
    deck_size: int
    failure_breakdown: FailureBreakdown | None = None

    def percent(self) -> float:
        return self.probability * 100.0


def _find_missing_colors(
    hearts_total: Dict[Color, int],
    wildcard_hearts: int,
    requirements: Dict[Color, int],
) -> List[str]:
    """คืน list ของ color.value ที่ขาด (เฉพาะ specific color, ไม่รวม gray)"""
    wildcards_left = wildcard_hearts
    missing = []
    for color, req in requirements.items():
        if color == Color.GRAY:
            continue
        have = hearts_total.get(color, 0)
        if have >= req:
            continue
        shortfall = req - have
        if wildcards_left >= shortfall:
            wildcards_left -= shortfall
        else:
            missing.append(color.value)
    return missing


def _build_card_list(composition, extra_exclude: List[str] | None = None) -> List[str]:
    """แปลง DeckComposition หรือ WaitingRoom เป็น list of tag strings สำหรับ sampling."""
    cards: List[str] = []
    for color in Color.trigger_colors():
        cards.extend([color.value] * composition.count(color))
    cards.extend(["all"] * composition.all_trigger)
    cards.extend(["non"] * composition.non_trigger)
    if extra_exclude:
        for tag in extra_exclude:
            if tag in cards:
                cards.remove(tag)
    return cards


def simulate_live(state: GameState, trials: int = 20000, seed: int | None = None) -> SimulationResult:
    """
    Run Monte Carlo simulation of the Yell phase.

    รองรับ Mid-Yell Reshuffle: ถ้า blade_count > deck ที่เหลือ จะ reshuffle waiting room
    (ไม่รวมใบที่ Yell ออกไปแล้วในรอบนี้) แล้ว draw ต่อจนครบ blade_count
    """
    rng = random.Random(seed)
    remaining = state.remaining_deck()
    N = remaining.total()
    draws = state.stage.blade_count

    if draws <= 0:
        combined = state.combined_requirements()
        satisfied = _check_hearts_satisfy(
            hearts_by_color=state.stage.basic_hearts,
            wildcard_hearts=0,
            requirements=combined,
        )
        return SimulationResult(
            probability=1.0 if satisfied else 0.0,
            successes=trials if satisfied else 0,
            trials=trials,
            draws=0,
            deck_size=N,
        )

    deck_list = _build_card_list(remaining)
    reshuffle_src = state.reshuffle_pool if state.reshuffle_pool is not None else state.waiting_room
    waiting_list = _build_card_list(reshuffle_src)
    will_reshuffle = draws > N

    combined_req = state.combined_requirements()
    successes = 0

    fail_specific: Dict[str, int] = {}
    fail_total_hearts = 0
    fail_multiple = 0

    for _ in range(trials):
        drawn: Dict[Color, int] = {}
        all_drawn = 0

        if not will_reshuffle:
            sample = rng.sample(deck_list, draws)
            yelled = sample
        else:
            phase1 = list(deck_list)
            rng.shuffle(phase1)

            remaining_wl = list(waiting_list)
            for tag in phase1:
                if tag in remaining_wl:
                    remaining_wl.remove(tag)

            still_needed = draws - len(phase1)
            if still_needed > len(remaining_wl):
                still_needed = len(remaining_wl)

            phase2 = rng.sample(remaining_wl, still_needed) if still_needed > 0 else []
            yelled = phase1 + phase2

        for tag in yelled:
            if tag == "all":
                all_drawn += 1
            elif tag != "non":
                color = Color(tag)
                drawn[color] = drawn.get(color, 0) + 1

        hearts_total: Dict[Color, int] = {
            color: state.stage.hearts_for_color(color) + drawn.get(color, 0)
            for color in Color.trigger_colors()
        }

        if _check_hearts_satisfy(
            hearts_by_color=hearts_total,
            wildcard_hearts=all_drawn,
            requirements=combined_req,
        ):
            successes += 1
        else:
            missing_colors = _find_missing_colors(hearts_total, all_drawn, combined_req)
            total_collected = sum(hearts_total.values()) + all_drawn
            total_required = sum(combined_req.values())

            if missing_colors:
                if len(missing_colors) > 1:
                    fail_multiple += 1
                else:
                    key = missing_colors[0]
                    fail_specific[key] = fail_specific.get(key, 0) + 1
            elif total_collected < total_required:
                fail_total_hearts += 1
            else:
                fail_multiple += 1

    breakdown = FailureBreakdown(
        missing_specific_color=fail_specific,
        missing_total_hearts=fail_total_hearts,
        multiple_causes=fail_multiple,
    )

    return SimulationResult(
        probability=successes / trials if trials else 0,
        successes=successes,
        trials=trials,
        draws=draws,
        deck_size=N,
        failure_breakdown=breakdown,
    )
