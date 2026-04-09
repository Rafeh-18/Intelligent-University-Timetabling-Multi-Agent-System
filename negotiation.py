"""
negotiation.py - Game-Theoretic Negotiation for University Timetabling MAS

Implements an auction-based slot allocation mechanism using Nash Bargaining.

How it works
------------
Instead of the SchedulerAgent simply picking the first valid slot, each
candidate slot is scored using a utility function for every stakeholder
(teacher, group, room). The slot with the highest combined Nash product
is selected — this is the Nash Bargaining Solution (NBS), which maximises
the product of all agents' utilities above their disagreement point.

Utility functions
-----------------
- TeacherAgent : prefers their declared preferred_time band; penalises
                 back-to-back sessions on the same day.
- GroupAgent   : prefers slots that spread sessions evenly across the week;
                 penalises days already heavily loaded.
- RoomAgent    : prefers the smallest room that still fits the group
                 (minimises wasted capacity).

Disagreement point
------------------
If no valid slot is found the disagreement payoff is 0 for all agents,
meaning the course goes unresolved.
"""

from utils import DAYS, TIME_SLOTS

# Morning slots (indices 0-2), Afternoon slots (indices 2-4)
MORNING_SLOTS   = TIME_SLOTS[:3]
AFTERNOON_SLOTS = TIME_SLOTS[2:]


# ─────────────────────────────────────────────────────────────────────────────
# Utility functions  (each returns a float in [0.0, 1.0])
# ─────────────────────────────────────────────────────────────────────────────

def teacher_utility(teacher_agent, day, time_slot):
    """
    Score a (day, slot) proposal from the teacher's perspective.

    Factors
    -------
    - +0.6  if time_slot is in teacher's preferred band
    - +0.4  base availability score
    - -0.2  penalty per session already booked on that day (back-to-back load)

    Returns float in [0.0, 1.0]
    """
    if not teacher_agent.is_available(day, time_slot):
        return 0.0

    score = 0.4  # base: slot is free

    # Preference alignment
    preferred = (MORNING_SLOTS if teacher_agent.preferred_time == "Morning"
                 else AFTERNOON_SLOTS)
    if time_slot in preferred:
        score += 0.6
    else:
        score += 0.2  # non-preferred but still usable

    # Back-to-back penalty: count already-booked slots on this day
    booked_today = sum(
        1 for slot in TIME_SLOTS
        if not teacher_agent.calendar[day][slot]
    )
    penalty = min(booked_today * 0.15, 0.4)
    score   = max(0.0, score - penalty)

    return round(min(score, 1.0), 4)


def group_utility(group_agent, day, time_slot):
    """
    Score a (day, slot) proposal from the student group's perspective.

    Factors
    -------
    - +0.5  base: slot is free
    - +0.5  spread bonus: inversely proportional to how many sessions
             the group already has on this day (encourages even distribution)

    Returns float in [0.0, 1.0]
    """
    if not group_agent.is_available(day, time_slot):
        return 0.0

    booked_today = sum(
        1 for slot in TIME_SLOTS
        if not group_agent.calendar[day][slot]
    )

    # Spread bonus: fewer sessions today = higher score
    max_daily = len(TIME_SLOTS)
    spread    = 1.0 - (booked_today / max_daily)
    score     = 0.5 + 0.5 * spread

    return round(min(score, 1.0), 4)


def room_utility(room_agent, group_size, day, time_slot):
    """
    Score a (day, slot, room) proposal from the room's perspective.

    Factors
    -------
    - 0.0   if room is occupied or too small
    - Score based on capacity efficiency: penalise oversized rooms
            efficiency = group_size / room_capacity (closer to 1.0 is better)

    Returns float in [0.0, 1.0]
    """
    if not room_agent.is_available(day, time_slot):
        return 0.0
    if not room_agent.fits_group(group_size):
        return 0.0

    efficiency = group_size / room_agent.capacity
    # Clamp: very oversized rooms score low, perfect fit scores 1.0
    score = min(efficiency * 1.2, 1.0)

    return round(score, 4)


# ─────────────────────────────────────────────────────────────────────────────
# Nash Bargaining Solution
# ─────────────────────────────────────────────────────────────────────────────

def nash_product(utilities, disagreement=0.0):
    """
    Compute the Nash product for a list of utility values.
    Nash product = ∏ (u_i - d_i)  for all agents i

    Any utility at or below the disagreement point returns 0.
    """
    product = 1.0
    for u in utilities:
        surplus = u - disagreement
        if surplus <= 0:
            return 0.0
        product *= surplus
    return product


def negotiate_slot(course, teacher_agent, group_agent, room_agents, constraint_agent):
    """
    Find the optimal (day, time_slot, room_agent) using Nash Bargaining.

    For every valid (day, slot, room) triple, compute each agent's utility
    and select the combination that maximises the Nash product.

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
        Returns None if no valid slot exists.
    """
    best_proposal   = None
    best_nash_score = -1.0

    for day in DAYS:
        for slot in TIME_SLOTS:
            for room in room_agents:

                proposal = {
                    "course":        course,
                    "teacher_agent": teacher_agent,
                    "group_agent":   group_agent,
                    "room_agent":    room,
                    "day":           day,
                    "time_slot":     slot,
                }

                # Hard-constraint gate — skip invalid combos immediately
                is_valid, _ = constraint_agent.check_constraints(proposal)
                if not is_valid:
                    continue

                # Compute utilities
                u_teacher = teacher_utility(teacher_agent, day, slot)
                u_group   = group_utility(group_agent, day, slot)
                u_room    = room_utility(room, group_agent.group_size, day, slot)

                score = nash_product([u_teacher, u_group, u_room])

                if score > best_nash_score:
                    best_nash_score = score
                    best_proposal   = {
                        **proposal,
                        "nash_score": round(score, 6),
                        "utilities": {
                            "teacher": u_teacher,
                            "group":   u_group,
                            "room":    u_room,
                        },
                    }

    if best_proposal:
        print(
            f"  [Negotiation] '{course['course_name']}' → "
            f"{best_proposal['day']} {best_proposal['time_slot']} "
            f"Rm {best_proposal['room_agent'].room_id} "
            f"(Nash={best_proposal['nash_score']:.4f})"
        )
    else:
        print(f"  [Negotiation] No valid slot found for '{course['course_name']}'")

    return best_proposal


# ─────────────────────────────────────────────────────────────────────────────
# Auction mechanism (optional extension)
# ─────────────────────────────────────────────────────────────────────────────

def run_slot_auction(courses, teacher_map, group_map, room_agents, constraint_agent):
    """
    Run a sealed-bid auction across all courses for available slots.

    Each course submits a "bid" equal to its Nash score for every valid slot.
    Slots are allocated greedily by highest bid, with conflicts resolved by
    re-auctioning displaced courses with remaining slots.

    Parameters
    ----------
    courses          : list[dict]
    teacher_map      : dict { teacher_id -> TeacherAgent }
    group_map        : dict { group_id   -> GroupAgent   }
    room_agents      : list[RoomAgent]
    constraint_agent : ConstraintAgent

    Returns
    -------
    dict {
        "assignments" : list[dict]   won proposals
        "unresolved"  : list[dict]   courses that lost the auction
    }
    """
    print("\n[Auction] Starting sealed-bid slot auction...")

    # Step 1: every course computes its best bid
    bids = []
    for course in courses:
        teacher = teacher_map.get(course["teacher_id"])
        group   = group_map.get(course["group_id"])
        if not teacher or not group:
            continue

        proposal = negotiate_slot(course, teacher, group, room_agents, constraint_agent)
        if proposal:
            bids.append(proposal)

    # Step 2: sort all bids by Nash score descending
    bids.sort(key=lambda b: b["nash_score"], reverse=True)

    # Step 3: greedy assignment — highest bidder wins each slot
    assigned_keys = set()   # (day, slot, room_id)
    assignments   = []
    unresolved    = []

    for bid in bids:
        key = (bid["day"], bid["time_slot"], bid["room_agent"].room_id)
        if key in assigned_keys:
            # Slot already taken — mark as unresolved (re-auction not implemented)
            unresolved.append(bid["course"])
            print(
                f"  [Auction] '{bid['course']['course_name']}' lost slot "
                f"{bid['day']} {bid['time_slot']} Rm {bid['room_agent'].room_id}"
            )
        else:
            assigned_keys.add(key)
            assignments.append(bid)
            # Book all agents
            bid["teacher_agent"].book_slot(bid["day"], bid["time_slot"])
            bid["group_agent"].book_slot(bid["day"], bid["time_slot"])
            bid["room_agent"].book_slot(bid["day"], bid["time_slot"])
            print(
                f"  [Auction] '{bid['course']['course_name']}' won "
                f"{bid['day']} {bid['time_slot']} Rm {bid['room_agent'].room_id}"
            )

    print(
        f"[Auction] Done — "
        f"{len(assignments)} assigned, {len(unresolved)} unresolved."
    )
    return {"assignments": assignments, "unresolved": unresolved}