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
class SimulationResult:
    probability: float
    successes: int
    trials: int
    draws: int
    deck_size: int

    def percent(self) -> float:
        return self.probability * 100.0


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

    for _ in range(trials):
        drawn: Dict[Color, int] = {}
        all_drawn = 0

        if not will_reshuffle:
            # กรณีปกติ: draw จาก deck เพียง pool เดียว
            sample = rng.sample(deck_list, draws)
            yelled = sample
        else:
            # Phase 1: draw การ์ดที่เหลือใน deck ออกมาทั้งหมด
            phase1 = list(deck_list)
            rng.shuffle(phase1)

            # Phase 2: reshuffle waiting room (ลบใบที่ Yell ออกไปแล้วใน phase 1)
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

    return SimulationResult(
        probability=successes / trials if trials else 0,
        successes=successes,
        trials=trials,
        draws=draws,
        deck_size=N,
    )
