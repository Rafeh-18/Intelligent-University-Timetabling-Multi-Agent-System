"""
scheduler.py - Core scheduling entry point and validation utilities

generate_timetable() is the single public entry point for the Flask layer.
Validation utilities check the final schedule for hard-constraint violations.
"""

from __future__ import annotations

from config import DAYS, TIME_SLOTS
from database import (
    get_all_teachers,
    get_all_groups,
    get_all_classrooms,
    get_all_courses,
    clear_schedule,
)
from model import TimetablingModel


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_timetable(
    courses:    list[dict] | None = None,
    teachers:   list[dict] | None = None,
    groups:     list[dict] | None = None,
    classrooms: list[dict] | None = None,
    use_negotiation: bool = True,
) -> dict:
    """
    Generate a new timetable from scratch.

    Steps
    -----
    1. Load data from DB (unless caller supplies it directly).
    2. Validate that the DB has the minimum required entities.
    3. Clear the existing schedule.
    4. Build the MAS model and run one step.
    5. Return timetable + summary + negotiation log.

    Parameters
    ----------
    courses / teachers / groups / classrooms:
        Pre-loaded data (optional). If None, fetched from the DB.
    use_negotiation : bool
        True  → NegotiatingSchedulerAgent (Nash + ML)
        False → basic SchedulerAgent (first-fit)

    Returns
    -------
    dict {
        "timetable":   list[dict],
        "summary":     dict,
        "negotiation": dict,
        "steps_run":   int,
    }
    """
    teachers   = teachers   or get_all_teachers()
    groups     = groups     or get_all_groups()
    classrooms = classrooms or get_all_classrooms()
    courses    = courses    or get_all_courses()

    # Validation before wiping the existing schedule
    if not teachers:
        raise ValueError("No teachers found in the database. Run load_sample_data() first.")
    if not groups:
        raise ValueError("No student groups found in the database.")
    if not classrooms:
        raise ValueError("No classrooms found in the database.")
    if not courses:
        print("[Scheduler] No courses found — nothing to schedule.")
        return {"timetable": [], "summary": {}, "negotiation": {}, "steps_run": 0}

    print(f"[Scheduler] Clearing previous schedule...")
    clear_schedule()

    print(f"[Scheduler] Building model — {len(courses)} courses to schedule...")
    model = TimetablingModel(teachers, groups, classrooms, courses,
                             use_negotiation=use_negotiation)
    model.step()

    results = model.get_results()
    scheduled = results["summary"].get("scheduled", 0)
    total     = results["summary"].get("total_courses", len(courses))
    print(
        f"[Scheduler] Finished — {scheduled}/{total} sessions created "
        f"({results['summary'].get('unresolved', 0)} unresolved)."
    )
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Slot helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_available_slots(agent, day: str | None = None) -> list[tuple[str, str]]:
    """
    Return a list of (day, slot) pairs where the agent is free.
    Works for TeacherAgent, GroupAgent, or RoomAgent.
    """
    days_to_check = [day] if day else DAYS
    return [
        (d, slot)
        for d in days_to_check
        for slot in TIME_SLOTS
        if agent.is_available(d, slot)
    ]


def find_valid_room(
    room_agents: list,
    required_type: str,
    day: str,
    time_slot: str,
    group_size: int = 0,
):
    """
    Return the first room that matches type, fits the group, and is free.
    Returns None if no suitable room exists.
    """
    return next(
        (
            r for r in room_agents
            if r.matches_type(required_type)
            and r.fits_group(group_size)
            and r.is_available(day, time_slot)
        ),
        None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Conflict detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_conflicts(schedule: list[dict]) -> list[dict]:
    """
    Scan the final schedule for three types of hard violations:

    A — Two sessions in the same room at the same time
    B — One teacher in two places at the same time
    C — One student group in two places at the same time

    Returns a list of conflict dicts (empty if the schedule is clean).
    """
    conflicts: list[dict] = []
    room_idx:    dict = {}
    teacher_idx: dict = {}
    group_idx:   dict = {}

    for session in schedule:
        day  = session["day"]
        slot = session["time_slot"]

        # ── Room
        rk = (day, slot, session["room_id"])
        if rk in room_idx:
            conflicts.append({
                "type":        "A",
                "description": f"Room {session['room_id']} double-booked at {day} {slot}",
                "sessions":    [room_idx[rk], session],
            })
        else:
            room_idx[rk] = session

        # ── Teacher
        tk = (day, slot, session["teacher_name"])
        if tk in teacher_idx:
            conflicts.append({
                "type":        "B",
                "description": f"Teacher '{session['teacher_name']}' double-booked at {day} {slot}",
                "sessions":    [teacher_idx[tk], session],
            })
        else:
            teacher_idx[tk] = session

        # ── Group
        label = f"{session['group_program']} Y{session['group_year']}"
        gk    = (day, slot, label)
        if gk in group_idx:
            conflicts.append({
                "type":        "C",
                "description": f"Group '{label}' double-booked at {day} {slot}",
                "sessions":    [group_idx[gk], session],
            })
        else:
            group_idx[gk] = session

    return conflicts


# ─────────────────────────────────────────────────────────────────────────────
# Validation report
# ─────────────────────────────────────────────────────────────────────────────

def validate_schedule(schedule: list[dict], total_courses: int | None = None) -> dict:
    """
    Generate a full quality-control report.

    Parameters
    ----------
    schedule      : output of database.get_schedule()
    total_courses : number of courses that should have been scheduled
                    (used to compute coverage %). If None, only scheduled
                    count is reported.

    Returns
    -------
    dict {
        "is_valid":        bool,
        "total_sessions":  int,
        "course_coverage": int,   distinct course names in schedule
        "coverage_pct":    float | None,
        "conflicts":       list[dict],
        "invalid_entries": list[dict],
        "report":          str,   human-readable summary
    }
    """
    conflicts      = detect_conflicts(schedule)
    invalid_entries: list[dict] = []

    for session in schedule:
        if session.get("day") not in DAYS:
            invalid_entries.append({**session, "reason": "Invalid day"})
        elif session.get("time_slot") not in TIME_SLOTS:
            invalid_entries.append({**session, "reason": "Invalid time_slot"})

    course_coverage = len({s["course_name"] for s in schedule})
    coverage_pct    = (
        round(course_coverage / total_courses * 100, 1)
        if total_courses
        else None
    )
    is_valid = len(conflicts) == 0 and len(invalid_entries) == 0

    lines = [
        "=" * 56,
        "  SCHEDULE VALIDATION REPORT",
        "=" * 56,
        f"  Total sessions    : {len(schedule)}",
        f"  Distinct courses  : {course_coverage}"
        + (f" / {total_courses} ({coverage_pct}%)" if total_courses else ""),
        f"  Hard conflicts    : {len(conflicts)}",
        f"  Invalid entries   : {len(invalid_entries)}",
        f"  Overall status    : {'✓ VALID' if is_valid else '✗ INVALID'}",
        "=" * 56,
    ]
    report = "\n".join(lines)
    print(report)

    return {
        "is_valid":        is_valid,
        "total_sessions":  len(schedule),
        "course_coverage": course_coverage,
        "coverage_pct":    coverage_pct,
        "conflicts":       conflicts,
        "invalid_entries": invalid_entries,
        "report":          report,
    }
