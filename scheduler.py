"""
scheduler.py - Core scheduling logic for University Timetabling MAS

This module is the high-level manager. It starts the simulation, 
finds empty rooms, and double-checks everything for mistakes.
"""

from database import (
    get_all_teachers,
    get_all_groups,
    get_all_classrooms,
    get_all_courses,
    clear_schedule,
)
from model import TimetablingModel
from utils import DAYS, TIME_SLOTS


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_timetable(courses=None, teachers=None, groups=None, classrooms=None):
    """
    The Big Red Button: Call this to create a brand new university schedule.
    It wipes the old data, builds the MAS model, and runs the simulation.
    """
    # 1. Gather all necessary data from the database if not provided
    teachers   = teachers   or get_all_teachers()
    groups     = groups     or get_all_groups()
    classrooms = classrooms or get_all_classrooms()
    courses    = courses    or get_all_courses()

    if not courses:
        print("[Scheduler] No courses found — nothing to schedule.")
        return {"timetable": [], "summary": {}, "steps_run": 0}

    # 2. Reset: Delete any old timetable entries before starting
    print(f"[Scheduler] Clearing previous schedule...")
    clear_schedule()

    # 3. Execution: Create the Multi-Agent System (Model) and run it
    print(f"[Scheduler] Building model with {len(courses)} courses...")
    model = TimetablingModel(teachers, groups, classrooms, courses)

    # One 'step' triggers the SchedulerAgent to place all courses
    model.step()

    # 4. Collection: Return the final timetable and stats
    results = model.get_results()
    print(f"[Scheduler] Finished — {results['summary'].get('scheduled', 0)} sessions created.")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Slot utilities (Helpers)
# ─────────────────────────────────────────────────────────────────────────────

def get_available_slots(agent, day=None):
    """
    A helper function to find 'white space' on an agent's calendar.
    Returns a list like [('Monday', '08:00'), ('Tuesday', '10:00')].
    """
    days_to_check = [day] if day else DAYS
    free_slots = []

    for d in days_to_check:
        for slot in TIME_SLOTS:
            # Polymorphism: works for TeacherAgent, GroupAgent, or RoomAgent
            if agent.is_available(d, slot):
                free_slots.append((d, slot))

    return free_slots


def find_valid_room(room_agents, required_type, day, time_slot, group_size=0):
    """
    Searches through all RoomAgents to find a room that:
    1. Is the right type (Lab/Lecture)
    2. Can fit all students
    3. Is currently empty
    """
    for room in room_agents:
        if (
            room.matches_type(required_type)
            and room.fits_group(group_size)
            and room.is_available(day, time_slot)
        ):
            return room
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Conflict detection & resolution (The 'Auditor')
# ─────────────────────────────────────────────────────────────────────────────

def detect_conflicts(schedule):
    """
    Checks the final schedule for three 'Sinful' errors:
    Type A: Two classes in one room at the same time.
    Type B: One teacher in two places at the same time.
    Type C: One group of students in two places at the same time.
    """
    conflicts = []

    # These dictionaries help us spot duplicates quickly
    room_index    = {}  # Tracks (Day, Slot, Room)
    teacher_index = {}  # Tracks (Day, Slot, Teacher)
    group_index   = {}  # Tracks (Day, Slot, Group)

    for session in schedule:
        day  = session["day"]
        slot = session["time_slot"]

        # Check Room Double-booking
        room_key = (day, slot, session["room_id"])
        if room_key in room_index:
            conflicts.append({
                "type": "A",
                "description": f"Room {session['room_id']} double-booked",
                "sessions": [room_index[room_key], session],
            })
        else:
            room_index[room_key] = session

        # Check Teacher Double-booking
        t_key = (day, slot, session["teacher_name"])
        if t_key in teacher_index:
            conflicts.append({
                "type": "B",
                "description": f"Teacher '{session['teacher_name']}' double-booked",
                "sessions": [teacher_index[t_key], session],
            })
        else:
            teacher_index[t_key] = session

        # Check Student Group Double-booking
        group_label = f"{session['group_program']} Y{session['group_year']}"
        g_key = (day, slot, group_label)
        if g_key in group_index:
            conflicts.append({
                "type": "C",
                "description": f"Group '{group_label}' double-booked",
                "sessions": [group_index[g_key], session],
            })
        else:
            group_index[g_key] = session

    return conflicts


def resolve_conflicts(schedule, conflicts):
    """
    Strategy: If two classes clash, keep the older one (lower ID)
    and flag the newer one to be re-scheduled later.
    """
    flagged_ids = set()

    for conflict in conflicts:
        # Sort clashing sessions by ID
        sessions = sorted(conflict["sessions"], key=lambda s: s["session_id"])
        # Flag the second session (the 'winner' stays, the 'loser' is flagged)
        flagged_ids.add(sessions[1]["session_id"])

    # Return the sessions that need to be fixed
    return [s for s in schedule if s["session_id"] in flagged_ids]


# ─────────────────────────────────────────────────────────────────────────────
# Validation report
# ─────────────────────────────────────────────────────────────────────────────

def validate_schedule(schedule):
    """
    Creates a full quality-control report.
    Checks for conflicts and ensures the days/times are valid strings.
    """
    conflicts        = detect_conflicts(schedule)
    invalid_sessions = []

    for session in schedule:
        # Check if the day is actually a day (not 'Potato')
        if session.get("day") not in DAYS:
            invalid_sessions.append({**session, "reason": "Invalid day"})
        # Check if the time slot is valid
        elif session.get("time_slot") not in TIME_SLOTS:
            invalid_sessions.append({**session, "reason": "Invalid time slot"})

    # How many distinct courses actually got a time slot?
    course_coverage = len({s["course_name"] for s in schedule})
    is_valid        = len(conflicts) == 0 and len(invalid_sessions) == 0

    # Build a nice text report for the console
    report_lines = [
        "=" * 50,
        "  SCHEDULE VALIDATION REPORT",
        "=" * 50,
        f"  Total sessions   : {len(schedule)}",
        f"  Course coverage  : {course_coverage} courses",
        f"  Hard conflicts   : {len(conflicts)}",
        f"  Overall status   : {'VALID ' if is_valid else 'INVALID '}",
        "=" * 50,
    ]
    report = "\n".join(report_lines)
    print(report)

    return {
        "is_valid": is_valid,
        "total_sessions": len(schedule),
        "conflicts": conflicts,
        "report": report,
    }