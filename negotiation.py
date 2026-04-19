"""
negotiation.py - Game-Theoretic Negotiation for University Timetabling MAS

Implements Nash Bargaining Solution (NBS) for slot allocation.

How it works
------------
For every valid (day, slot, room) triple, each stakeholder (teacher, group, room)
assigns a utility score in [0, 1]. The triple that maximises the Nash product —
the product of all utilities above each agent's disagreement point (0) — is
selected. This is the NBS: it is Pareto-optimal and fair.

If no valid triple is found, the disagreement payoff is 0 (course goes unscheduled).

Utility functions
-----------------
- teacher_utility  : prefers declared time band; penalises back-to-back load
- group_utility    : prefers days with fewer existing sessions (spread)
- room_utility     : prefers the smallest room that fits (capacity efficiency)

All weights are in config.py — no magic numbers here.
"""

from __future__ import annotations

from config import (
    DAYS,
    TIME_SLOTS,
    MORNING_SLOTS,
    AFTERNOON_SLOTS,
    TEACHER_W,
    GROUP_W,
    ROOM_W,
)


# ─────────────────────────────────────────────────────────────────────────────
# Per-agent utility functions
# ─────────────────────────────────────────────────────────────────────────────

def teacher_utility(teacher_agent, day: str, time_slot: str) -> float:
    """
    Score (day, slot) from the teacher's perspective.

    Scoring
    -------
    BASE_SCORE
        + PREFERRED_BONUS   if slot is in declared preferred band
        + NON_PREFERRED_BONUS  otherwise
        - DAILY_LOAD_PENALTY × sessions_already_booked_today (capped)

    Returns float in [0.0, 1.0].
    """
    if not teacher_agent.is_available(day, time_slot):
        return 0.0

    score = TEACHER_W.BASE_SCORE

    preferred = (
        MORNING_SLOTS if teacher_agent.preferred_time == "Morning"
        else AFTERNOON_SLOTS
    )
    score += (
        TEACHER_W.PREFERRED_BONUS
        if time_slot in preferred
        else TEACHER_W.NON_PREFERRED_BONUS
    )

    booked_today = teacher_agent.sessions_on_day(day)
    penalty      = min(booked_today * TEACHER_W.DAILY_LOAD_PENALTY,
                       TEACHER_W.MAX_DAILY_PENALTY)
    score        = max(0.0, score - penalty)

    return round(min(score, 1.0), 4)


def group_utility(group_agent, day: str, time_slot: str) -> float:
    """
    Score (day, slot) from the student group's perspective.

    Scoring
    -------
    BASE_SCORE
        + SPREAD_BONUS × (1 - booked_today / max_daily_slots)

    A day with no sessions scores the full SPREAD_BONUS.
    A fully-booked day scores 0 on the spread component.

    Returns float in [0.0, 1.0].
    """
    if not group_agent.is_available(day, time_slot):
        return 0.0

    max_daily  = len(TIME_SLOTS)
    booked_today = group_agent.sessions_on_day(day)
    spread     = 1.0 - (booked_today / max_daily)
    score      = GROUP_W.BASE_SCORE + GROUP_W.SPREAD_BONUS * spread

    return round(min(score, 1.0), 4)


def room_utility(room_agent, group_size: int, day: str, time_slot: str) -> float:
    """
    Score (day, slot, room) from the room's perspective.

    Scoring
    -------
    0.0 if occupied or too small.
    capacity_efficiency = group_size / room_capacity, multiplied by
    EFFICIENCY_MULTIPLIER and capped at 1.0.

    A perfect-fit room (group fills it) scores ≈ 1.0.
    An oversized room (e.g., 16 students in a 32-seat hall) scores ≈ 0.6.

    Returns float in [0.0, 1.0].
    """
    if not room_agent.is_available(day, time_slot):
        return 0.0
    if not room_agent.fits_group(group_size):
        return 0.0

    efficiency = group_size / room_agent.capacity
    score      = min(efficiency * ROOM_W.EFFICIENCY_MULTIPLIER, 1.0)

    return round(score, 4)


# ─────────────────────────────────────────────────────────────────────────────
# Nash Bargaining Solution
# ─────────────────────────────────────────────────────────────────────────────

def nash_product(utilities: list[float], disagreement: float = 0.0) -> float:
    """
    Compute the Nash product: ∏ (u_i − d_i) for all agents i.

    Any utility at or below the disagreement point causes the product to
    collapse to 0 (no deal is better than disagreement for all parties).

    Parameters
    ----------
    utilities    : list of per-agent utility scores
    disagreement : disagreement payoff (default 0.0)

    Returns
    -------
    float ≥ 0.0
    """
    product = 1.0
    for u in utilities:
        surplus = u - disagreement
        if surplus <= 0.0:
            return 0.0
        product *= surplus
    return product


def negotiate_slot(
    course: dict,
    teacher_agent,
    group_agent,
    room_agents: list,
    constraint_agent,
) -> dict | None:
    """
    Find the optimal (day, slot, room) triple using Nash Bargaining.

    For every valid triple this function:
      1. Verifies hard constraints via constraint_agent.
      2. Computes per-agent utilities.
      3. Computes the Nash product.
    Returns the triple with the maximum Nash product.

    Parameters
    ----------
    course           : dict
    teacher_agent    : TeacherAgent
    group_agent      : GroupAgent
    room_agents      : list[RoomAgent]
    constraint_agent : ConstraintAgent

    Returns
    -------
    dict | None
        Best proposal dict with keys:
            course, teacher_agent, group_agent, room_agent,
            day, time_slot, nash_score, utilities
        None if no valid slot exists.
    """
    best_proposal  = None
    best_nash      = -1.0

    # Pre-filter rooms for efficiency
    eligible_rooms = [
        r for r in room_agents
        if r.matches_type(course["required_room_type"])
        and r.fits_group(group_agent.group_size)
    ]

    for day in teacher_agent.available_days:
        for slot in TIME_SLOTS:
            if not teacher_agent.is_available(day, slot):
                continue
            if not group_agent.is_available(day, slot):
                continue

            for room in eligible_rooms:
                if not room.is_available(day, slot):
                    continue

                proposal = {
                    "course":        course,
                    "teacher_agent": teacher_agent,
                    "group_agent":   group_agent,
                    "room_agent":    room,
                    "day":           day,
                    "time_slot":     slot,
                }

                # Final hard-constraint gate (catches edge cases)
                is_valid, _ = constraint_agent.check_constraints(proposal)
                if not is_valid:
                    continue

                u_t = teacher_utility(teacher_agent, day, slot)
                u_g = group_utility(group_agent, day, slot)
                u_r = room_utility(room, group_agent.group_size, day, slot)

                score = nash_product([u_t, u_g, u_r])

                if score > best_nash:
                    best_nash = score
                    best_proposal = {
                        **proposal,
                        "nash_score": round(score, 6),
                        "utilities":  {"teacher": u_t, "group": u_g, "room": u_r},
                    }

    if best_proposal:
        print(
            f"  [Negotiation] '{course['course_name']}' → "
            f"{best_proposal['day']} {best_proposal['time_slot']} "
            f"Rm {best_proposal['room_agent'].room_id} "
            f"Nash={best_proposal['nash_score']:.4f}"
        )
    else:
        print(f"  [Negotiation] No valid slot for '{course['course_name']}'")

    return best_proposal


# ─────────────────────────────────────────────────────────────────────────────
# Sealed-bid auction  (optional extension)
# ─────────────────────────────────────────────────────────────────────────────

def run_slot_auction(
    courses: list[dict],
    teacher_map: dict,
    group_map: dict,
    room_agents: list,
    constraint_agent,
) -> dict:
    """
    Sealed-bid auction across all courses.

    Each course bids its best Nash score. Slots are allocated greedily
    (highest bidder wins). Because bids are computed on an unmodified calendar,
    conflict detection at assignment time checks teacher AND group conflicts —
    not just room conflicts — preventing double-booking.

    Returns
    -------
    dict {
        "assignments": list[dict],
        "unresolved":  list[dict],
    }
    """
    print("\n[Auction] Starting sealed-bid slot auction...")

    # Step 1 — every course computes its best bid on the current (empty) calendar
    bids: list[dict] = []
    for course in courses:
        teacher = teacher_map.get(course["teacher_id"])
        group   = group_map.get(course["group_id"])
        if not teacher or not group:
            continue
        proposal = negotiate_slot(course, teacher, group, room_agents, constraint_agent)
        if proposal:
            bids.append(proposal)

    # Step 2 — sort by Nash score descending
    bids.sort(key=lambda b: b["nash_score"], reverse=True)

    # Step 3 — greedy assignment with full conflict re-validation
    booked_room_slots:    set[tuple] = set()   # (day, slot, room_id)
    booked_teacher_slots: set[tuple] = set()   # (day, slot, teacher_id)
    booked_group_slots:   set[tuple] = set()   # (day, slot, group_id)

    assignments: list[dict] = []
    unresolved:  list[dict] = []

    for bid in bids:
        day      = bid["day"]
        slot     = bid["time_slot"]
        room_key    = (day, slot, bid["room_agent"].room_id)
        teacher_key = (day, slot, bid["teacher_agent"].teacher_id)
        group_key   = (day, slot, bid["group_agent"].group_id)

        conflict = (
            room_key    in booked_room_slots
            or teacher_key in booked_teacher_slots
            or group_key   in booked_group_slots
        )

        if conflict:
            unresolved.append(bid["course"])
            print(
                f"  [Auction] '{bid['course']['course_name']}' lost "
                f"{day} {slot} (conflict)"
            )
            continue

        # Win — record bookings
        booked_room_slots.add(room_key)
        booked_teacher_slots.add(teacher_key)
        booked_group_slots.add(group_key)

        # Book agent calendars
        bid["teacher_agent"].book_slot(day, slot)
        bid["group_agent"].book_slot(day, slot)
        bid["room_agent"].book_slot(day, slot)

        assignments.append(bid)
        print(
            f"  [Auction] '{bid['course']['course_name']}' won "
            f"{day} {slot} Rm {bid['room_agent'].room_id}"
        )

    print(
        f"[Auction] Done — "
        f"{len(assignments)} assigned, {len(unresolved)} unresolved."
    )
    return {"assignments": assignments, "unresolved": unresolved}
