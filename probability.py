"""
Hypergeometric probability calculation for Love Live OCG.

Key insight (from user's Google Sheet, verified to reproduce 90.85%):
   When Yell draws N cards from the remaining deck, a Live succeeds iff:
     1. For each non-Gray color C in requirements:
           (drawn C triggers) + (All triggers used for C) >= required C hearts
     2. Total hearts drawn (any trigger) + basic hearts on stage
           >= total required hearts (including gray)

   Equivalently:
     - Non-trigger cards drawn must be <= (N - hearts_still_needed_from_yell)
     - Target-color-compatible cards drawn must be >= target-color-still-needed
"""
from __future__ import annotations
from dataclasses import dataclass
from math import comb
from typing import Dict, List, Tuple

from models import Color, DeckComposition, GameState, WaitingRoom


@dataclass
class ProbabilityResult:
    probability: float            # 0.0 - 1.0
    favorable_cases: int          # Number of favorable (deck, draw) configurations
    total_cases: int              # Total possible draws = C(N, n)
    draws: int                    # Number of cards drawn (blade count)
    deck_size: int                # Effective deck size

    def percent(self) -> float:
        return self.probability * 100.0


def _multinomial_hypergeometric_prob(
    category_sizes: List[int],
    category_draws: List[int],
    total_deck: int,
    total_draws: int,
) -> float:
    """
    Probability of drawing exactly category_draws[i] cards from category of size
    category_sizes[i]. Uses multivariate hypergeometric.
    """
    if sum(category_draws) != total_draws:
        return 0.0
    num = 1
    for k, d in zip(category_sizes, category_draws):
        if d < 0 or d > k:
            return 0.0
        num *= comb(k, d)
    denom = comb(total_deck, total_draws)
    if denom == 0:
        return 0.0
    return num / denom


def calculate_live_success_probability(state: GameState) -> ProbabilityResult:
    """
    Calculate the exact probability that the player's Yell succeeds.

    Approach: enumerate all valid (drawn per category) tuples whose counts
    satisfy the success conditions, summing their multivariate hypergeometric
    probabilities. Uses the deck's remaining composition.
    """
    remaining = state.remaining_deck()
    N = remaining.total()
    draws = state.stage.blade_count

    # Edge cases
    if draws <= 0:
        # No yell — success iff basic hearts already cover requirements
        combined = state.combined_requirements()
        satisfied = _check_hearts_satisfy(
            hearts_by_color=state.stage.basic_hearts,
            wildcard_hearts=0,
            requirements=combined,
        )
        return ProbabilityResult(
            probability=1.0 if satisfied else 0.0,
            favorable_cases=1 if satisfied else 0,
            total_cases=1,
            draws=0,
            deck_size=N,
        )

    if draws > N:
        # Can't draw more than deck contains (would require reshuffle) — cap at N
        draws = N

    # Categorize the remaining deck
    # We split into categories: each trigger color, All, Non-trigger
    categories: List[Tuple[str, int]] = []
    category_map: Dict[str, int] = {}

    for color in Color.trigger_colors():
        cnt = remaining.count(color)
        categories.append((color.value, cnt))
        category_map[color.value] = len(categories) - 1

    all_idx = len(categories)
    categories.append(("all", remaining.all_trigger))
    non_idx = len(categories)
    categories.append(("non", remaining.non_trigger))

    combined_req = state.combined_requirements()
    total_required = sum(combined_req.values())
    total_basic = state.stage.total_basic_hearts()

    # Enumerate all ways to split `draws` among categories
    # Use a recursive/iterative approach; with up to ~7 categories, this is tractable
    category_counts = [c[1] for c in categories]

    favorable_prob = 0.0
    total_cases = comb(N, draws) if N >= draws else 0

    # Use iterative enumeration
    def enumerate_splits(idx: int, remaining_draws: int, current: List[int]):
        nonlocal favorable_prob
        if idx == len(categories) - 1:
            # Last category takes whatever's left
            last = remaining_draws
            if 0 <= last <= category_counts[idx]:
                current.append(last)
                # Check this split
                if _is_favorable(current, categories, state, combined_req):
                    # Compute probability of this exact split
                    num = 1
                    for k, d in zip(category_counts, current):
                        num *= comb(k, d)
                    favorable_prob += num / total_cases if total_cases else 0
                current.pop()
            return
        cat_size = category_counts[idx]
        max_take = min(remaining_draws, cat_size)
        for take in range(0, max_take + 1):
            current.append(take)
            enumerate_splits(idx + 1, remaining_draws - take, current)
            current.pop()

    if total_cases > 0:
        enumerate_splits(0, draws, [])

    favorable_cases = round(favorable_prob * total_cases)
    return ProbabilityResult(
        probability=favorable_prob,
        favorable_cases=favorable_cases,
        total_cases=total_cases,
        draws=draws,
        deck_size=N,
    )


def _is_favorable(
    drawn_per_cat: List[int],
    categories: List[Tuple[str, int]],
    state: GameState,
    combined_req: Dict[Color, int],
) -> bool:
    """
    Check if a given draw distribution satisfies the Live success condition:
      1. Each non-gray color's required hearts are met (trigger + all wildcards + basic)
      2. Total hearts >= total required (including gray)
    """
    # Build hearts drawn per color
    drawn_hearts: Dict[Color, int] = {}
    all_drawn = 0
    non_drawn = 0
    for (cat_name, _cat_size), taken in zip(categories, drawn_per_cat):
        if cat_name == "all":
            all_drawn = taken
        elif cat_name == "non":
            non_drawn = taken
        else:
            try:
                color = Color(cat_name)
                drawn_hearts[color] = taken
            except ValueError:
                pass

    # Try to satisfy requirements using basic hearts + drawn hearts + all-trigger wildcards
    return _check_hearts_satisfy(
        hearts_by_color={
            color: state.stage.hearts_for_color(color) + drawn_hearts.get(color, 0)
            for color in Color.trigger_colors()
        },
        wildcard_hearts=all_drawn,
        requirements=combined_req,
    )


def _check_hearts_satisfy(
    hearts_by_color: Dict[Color, int],
    wildcard_hearts: int,
    requirements: Dict[Color, int],
) -> bool:
    """
    Greedy check: can we satisfy each color requirement using specific-color hearts
    and wildcard (All) hearts, AND total hearts >= total required?

    Algorithm:
      1. For each non-gray color, specific hearts cover it first.
         Shortfall must be covered by wildcards.
      2. Any wildcards + leftover specific hearts cover gray requirement.
      3. Total collected must be >= total required.
    """
    wildcards_left = wildcard_hearts
    leftover_specifics = 0

    gray_required = requirements.get(Color.GRAY, 0)
    total_required = sum(requirements.values())
    total_collected = sum(hearts_by_color.values()) + wildcard_hearts

    # Step 1: cover each non-gray color
    for color, req in requirements.items():
        if color == Color.GRAY:
            continue
        have = hearts_by_color.get(color, 0)
        if have >= req:
            leftover_specifics += (have - req)
        else:
            shortfall = req - have
            if wildcards_left >= shortfall:
                wildcards_left -= shortfall
            else:
                return False  # Can't cover this specific color

    # Step 2: cover gray requirement with anything left
    pool_for_gray = wildcards_left + leftover_specifics + _unused_colors_total(
        hearts_by_color, requirements
    )
    # Actually simpler: total collected must be >= total required
    if total_collected < total_required:
        return False

    return True


def _unused_colors_total(
    hearts_by_color: Dict[Color, int],
    requirements: Dict[Color, int],
) -> int:
    """Sum of hearts in colors that aren't required at all."""
    required_colors = {c for c in requirements if c != Color.GRAY}
    return sum(n for c, n in hearts_by_color.items() if c not in required_colors)


def calculate_score_plus_probability(
    remaining_deck: DeckComposition,
    draws: int,
    min_hits: int = 1,
) -> float:
    """
    โอกาสที่จะ Yell เจอ Score+ Live card อย่างน้อย min_hits ใบ

    ใช้ hypergeometric: pool = score_plus_count ใน remaining deck
    P(เจอ ≥ k) = 1 - P(เจอ < k)
               = 1 - Σ_{i=0}^{k-1} C(sp, i) * C(N-sp, draws-i) / C(N, draws)
    """
    N = remaining_deck.total()
    sp = remaining_deck.score_plus_count
    draws = min(draws, N)

    if N == 0 or draws == 0 or sp == 0:
        return 0.0

    total_cases = comb(N, draws)
    if total_cases == 0:
        return 0.0

    prob_miss = sum(
        comb(sp, i) * comb(N - sp, draws - i)
        for i in range(min_hits)
        if draws - i <= N - sp
    ) / total_cases

    return max(0.0, 1.0 - prob_miss)


def compute_non_trigger_sensitivity(
    state: GameState,
    total_out: int | None = None,
    mc_trials: int = 20_000,
    mc_seed: int | None = 42,
) -> list[dict]:
    """
    จำลองสถานการณ์: กำหนดจำนวนการ์ดที่ออกจาก Deck รวม = total_out ใบ
    แล้ววนให้ Non-Trigger คงเหลือใน Deck ตั้งแต่ 0 ถึง deck.non_trigger ใบ

    สำหรับแต่ละ non_remaining (Non-Trigger ใน Deck):
      - non_wr = deck.non_trigger - non_remaining  (Non-Trigger ออกไปแล้ว)
      - trigger_wr_total = total_out - non_wr       (Trigger ออกไปแล้ว รวม)
      - กระจาย trigger_wr_total ตามสัดส่วน WR trigger ปัจจุบัน
        (ถ้า trigger_wr_total < 0 → ข้ามกรณีนี้เพราะเป็นไปไม่ได้)
      - แถวที่ตรงกับสถานการณ์ปัจจุบันของ User จะมี is_current = True

    total_out: ถ้าไม่ระบุ ใช้ state.waiting_room.total() (= สถานการณ์ปัจจุบัน)

    Return list of dicts:
        non_remaining  : int   — Non-Trigger ที่เหลือใน Deck
        trigger_wr     : int   — Trigger ที่ออกไป (รวม)
        non_wr         : int   — Non-Trigger ที่ออกไป
        deck_remaining : int   — Deck ที่เหลือทั้งหมด
        exact_pct      : float — Exact Hypergeometric (%)
        mc_pct         : float — Monte Carlo (%)
        is_current     : bool  — True = ตรงกับสถานการณ์ปัจจุบัน
    """
    from simulator import simulate_live

    if total_out is None:
        total_out = state.waiting_room.total()

    # trigger WR ปัจจุบัน (สัดส่วนสำหรับ distribute)
    current_trigger_wr = {c: state.waiting_room.count(c) for c in Color.trigger_colors()}
    current_all_wr = state.waiting_room.all_trigger
    current_trigger_wr_total = sum(current_trigger_wr.values()) + current_all_wr

    # non_remaining ปัจจุบัน
    current_non_remaining = state.deck.non_trigger - state.waiting_room.non_trigger

    rows = []
    for non_remaining in range(state.deck.non_trigger + 1):
        non_wr = state.deck.non_trigger - non_remaining
        trigger_wr_total = total_out - non_wr

        # ไม่สามารถมี trigger ออกไปติดลบ หรือเกินจำนวน trigger ทั้งหมดใน deck
        deck_trigger_total = state.deck.total() - state.deck.non_trigger
        if trigger_wr_total < 0 or trigger_wr_total > deck_trigger_total:
            continue

        # กระจาย trigger_wr_total ตามสัดส่วน WR ปัจจุบัน
        if current_trigger_wr_total > 0:
            ratio = trigger_wr_total / current_trigger_wr_total
            new_trigger_wr: dict[Color, int] = {}
            allocated = 0
            colors = list(Color.trigger_colors())
            for i, c in enumerate(colors):
                if i == len(colors) - 1:
                    new_trigger_wr[c] = max(0, min(
                        state.deck.count(c),
                        trigger_wr_total - allocated - max(0, round(current_all_wr * ratio))
                    ))
                else:
                    new_trigger_wr[c] = max(0, min(
                        state.deck.count(c),
                        round(current_trigger_wr.get(c, 0) * ratio)
                    ))
                    allocated += new_trigger_wr[c]
            new_all_wr = max(0, min(
                state.deck.all_trigger,
                trigger_wr_total - sum(new_trigger_wr.values())
            ))
        else:
            # ไม่มี trigger ใน WR ตอนนี้ — กระจาย trigger_wr_total เป็น all_trigger ก่อน แล้วค่อยสี
            new_trigger_wr = {c: 0 for c in Color.trigger_colors()}
            new_all_wr = min(state.deck.all_trigger, trigger_wr_total)
            remaining_trigger = trigger_wr_total - new_all_wr
            for c in Color.trigger_colors():
                take = min(state.deck.count(c), remaining_trigger)
                new_trigger_wr[c] = take
                remaining_trigger -= take
                if remaining_trigger == 0:
                    break

        modified_wr = WaitingRoom(
            trigger_counts=new_trigger_wr,
            all_trigger=new_all_wr,
            non_trigger=non_wr,
            score_plus_count=state.waiting_room.score_plus_count,
        )
        modified_state = GameState(
            deck=state.deck,
            waiting_room=modified_wr,
            stage=state.stage,
            lives=state.lives,
        )
        mod_remaining = modified_state.remaining_deck()

        exact_result = calculate_live_success_probability(modified_state)
        mc_result = simulate_live(modified_state, trials=mc_trials, seed=mc_seed)

        rows.append({
            "non_remaining": non_remaining,
            "trigger_wr": sum(new_trigger_wr.values()) + new_all_wr,
            "non_wr": non_wr,
            "deck_remaining": mod_remaining.total(),
            "exact_pct": exact_result.percent(),
            "mc_pct": mc_result.percent(),
            "is_current": non_remaining == current_non_remaining,
        })

    return rows


def simple_target_probability(
    remaining_deck: DeckComposition,
    target_color: Color,
    draws: int,
    target_needed: int,
    non_trigger_max: int,
) -> ProbabilityResult:
    """
    Simplified calculation matching the Google Sheet exactly:
      - Target color + All Trigger must be drawn >= target_needed
      - Non-Trigger drawn must be <= non_trigger_max
      - Other triggers (non-target) fill the rest freely
    """
    target_pool = remaining_deck.count(target_color) + remaining_deck.all_trigger
    other_trigger_pool = (
        sum(
            remaining_deck.count(c)
            for c in Color.trigger_colors()
            if c != target_color
        )
    )
    non_trigger_pool = remaining_deck.non_trigger
    N = target_pool + other_trigger_pool + non_trigger_pool

    if N == 0 or draws == 0 or draws > N:
        return ProbabilityResult(
            probability=0.0,
            favorable_cases=0,
            total_cases=comb(N, draws) if N >= draws else 0,
            draws=draws,
            deck_size=N,
        )

    total_cases = comb(N, draws)
    favorable = 0

    for n in range(0, min(non_trigger_max, non_trigger_pool) + 1):
        for r in range(target_needed, min(draws - n, target_pool) + 1):
            o = draws - n - r
            if 0 <= o <= other_trigger_pool:
                favorable += (
                    comb(target_pool, r)
                    * comb(other_trigger_pool, o)
                    * comb(non_trigger_pool, n)
                )

    prob = favorable / total_cases if total_cases else 0
    return ProbabilityResult(
        probability=prob,
        favorable_cases=favorable,
        total_cases=total_cases,
        draws=draws,
        deck_size=N,
    )
