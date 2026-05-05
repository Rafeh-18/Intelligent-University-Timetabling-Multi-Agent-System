"""
utils.py - Utility functions for University Timetabling MAS
Real data extracted from HIDE PI-2B timetables (Semester 1 & 2, AY 2025-2026)
"""

import csv
import os
from database import (
    init_db,
    insert_teacher,
    insert_group,
    insert_classroom,
    insert_course,
    get_all_teachers,
    get_all_groups,
    get_all_classrooms,
    get_all_courses,
)

# ── Days and time slots ───────────────────────────────────────────────────────
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

TIME_SLOTS = [
    "08:30-10:00",
    "10:15-11:45",
    "13:00-14:30",
    "14:45-16:15",
    "16:15-18:00",
]


def load_sample_data():
    """
    Populate the database with REAL data from HIDE PI-2B timetables
    Semester 1 & 2, Academic Year 2025-2026.

    Returns a dict with counts of each entity loaded.
    """
    init_db()
    counts = {"teachers": 0, "groups": 0, "classrooms": 0, "courses": 0}

    # ── Teachers ──────────────────────────────────────────────────────────────
    # Extracted from both timetable images
    # Format: (name, available_days, preferred_time)
    if not get_all_teachers():
        teachers = [
            # Semester 1 teachers
            ("A. Slimene",          "Monday,Wednesday",                      "Morning"),
            ("F. Zekri",            "Monday,Saturday",                       "Morning"),
            ("S. Zekri",            "Monday,Tuesday",                        "Afternoon"),
            ("A. Jarraya",          "Monday,Friday",                         "Afternoon"),
            ("F. Kardous",          "Tuesday,Thursday,Friday",               "Morning"),
            ("M. Denden",           "Tuesday,Thursday,Saturday",             "Morning"),
            ("A. Farji",            "Wednesday,Thursday",                    "Morning"),
            ("R. Bouslama",         "Thursday,Friday",                       "Afternoon"),
            ("I. Mtiri",            "Thursday,Friday",                       "Morning"),
            ("R. Benabderrahmane",  "Friday,Saturday",                       "Morning"),
            ("N. Semmar",           "Friday",                                "Morning"),
            ("L. Bouksaier",        "Friday",                                "Afternoon"),
            # Semester 2 teachers
            ("Mohamed Ali Cherni",  "Monday,Tuesday,Wednesday",              "Morning"),
            ("Souhir Zekri",        "Monday,Wednesday",                      "Morning"),
            ("Kaouther Nouira",     "Monday,Tuesday,Wednesday,Saturday",     "Afternoon"),
            ("Wided Guezguez",      "Tuesday,Wednesday",                     "Morning"),
            ("Imed Mitri",          "Tuesday,Wednesday",                     "Afternoon"),
            ("Eymen Errais",        "Tuesday,Friday,Saturday",               "Morning"),
            ("Mohsen Denden",       "Thursday,Saturday",                     "Morning"),
            ("Faten Kardous",       "Thursday,Friday",                       "Morning"),
            ("Roua Khelifi",        "Thursday",                              "Afternoon"),
            ("Wissem Nawar",        "Friday",                                "Afternoon"),
            ("Amel Jarraya",        "Friday",                                "Afternoon"),
        ]
        for name, days, pref in teachers:
            insert_teacher(name, days, pref)
        counts["teachers"] = len(teachers)
        print(f"[Utils] {len(teachers)} teachers loaded.")
    else:
        print("[Utils] Teachers already exist — skipping.")

    # ── Student Groups ────────────────────────────────────────────────────────
    if not get_all_groups():
        groups = [
            ("PI",  2, 16),   # PI 2-B  (main group, size ~16 per timetable)
            ("PI",  2, 16),   # PI 2-B subgroup A
            ("PI",  2, 16),   # PI 2-B subgroup B
        ]
        for program, year, size in groups:
            insert_group(program, year, size)
        counts["groups"] = len(groups)
        print(f"[Utils] {len(groups)} groups loaded.")
    else:
        print("[Utils] Groups already exist — skipping.")

    # ── Classrooms ────────────────────────────────────────────────────────────
    # Rooms extracted from timetable: CR17, CR18, L3, and general LEC rooms
    if not get_all_classrooms():
        classrooms = [
            (16, "Projector,Whiteboard",            ),   # CR17  — standard lecture
            (16, "Projector,Whiteboard",            ),   # CR18  — standard lecture
            (16, "Computers,Projector,Whiteboard",  ),   # L3    — computer lab
            (32, "Projector,Microphone,Whiteboard", ),   # Large lecture hall (LEC)
            (16, "Computers,Projector,Whiteboard",  ),   # Extra lab room
        ]
        for cap, equip in classrooms:
            insert_classroom(cap, equip)
        counts["classrooms"] = len(classrooms)
        print(f"[Utils] {len(classrooms)} classrooms loaded.")
    else:
        print("[Utils] Classrooms already exist — skipping.")

    # ── Courses ───────────────────────────────────────────────────────────────
    # Extracted from both semesters
    # Format: (course_name, teacher_id, group_id, required_room_type)
    # Teacher IDs match insertion order above (1-indexed)
    if not get_all_courses():
        courses = [
            # ── Semester 1 ────────────────────────────────────────────────────
            # teacher_id references: 1=A.Slimene, 2=F.Zekri, 3=S.Zekri,
            # 4=A.Jarraya, 5=F.Kardous, 6=M.Denden, 7=A.Farji,
            # 8=R.Bouslama, 9=I.Mtiri, 10=R.Benabderrahmane,
            # 11=N.Semmar, 12=L.Bouksaier

            ("Machine Learning (LEC)",                    1,  1, "Lecture Hall"),
            ("Machine Learning (Lab)",                    1,  2, "Lab"),
            ("UNIX Programming Environment (LEC)",        2,  1, "Lecture Hall"),
            ("UNIX Programming Environment (Lab)",        2,  3, "Lab"),
            ("Philosophy (LEC)",                          3,  1, "Lecture Hall"),
            ("Study Skills (LEC)",                        4,  1, "Lecture Hall"),
            ("Control System (LEC)",                      5,  1, "Lecture Hall"),
            ("Control System (TUT)",                      5,  2, "Standard"),
            ("Control System (Lab)",                      5,  3, "Lab"),
            ("Computer Networks (LEC)",                   6,  1, "Lecture Hall"),
            ("Computer Networks (Lab)",                   6,  2, "Lab"),
            ("Probability and Statistics 2 (LEC)",       11,  1, "Lecture Hall"),
            ("Probability and Statistics 2 (TUT)",        5,  2, "Standard"),
            ("Quantum Physics (LEC)",                     7,  1, "Lecture Hall"),
            ("Quantum Physics (TUT)",                     7,  2, "Standard"),
            ("Statistical Machine Learning (LEC)",        1,  1, "Lecture Hall"),
            ("Software Design & Architecture (LEC)",      8,  1, "Lecture Hall"),
            ("Software Design & Architecture (Lab)",      8,  2, "Lab"),
            ("Operational Research (LEC)",                9,  1, "Lecture Hall"),
            ("Operational Research (TUT)",                9,  2, "Standard"),
            ("Nanotechnology (LEC)",                     10,  1, "Lecture Hall"),
            ("Nanotechnology (Lab)",                     10,  3, "Lab"),
            ("Art History",                              12,  1, "Lecture Hall"),

            # ── Semester 2 ────────────────────────────────────────────────────
            # teacher_id references: 13=M.A.Cherni, 14=Souhir Zekri,
            # 15=K.Nouira, 16=W.Guezguez, 17=I.Mitri, 18=E.Errais,
            # 19=M.Denden, 20=F.Kardous, 21=R.Khelifi,
            # 22=W.Nawar, 23=A.Jarraya

            ("Microcontrollers (LEC)",                   13,  1, "Lecture Hall"),
            ("Microcontrollers (Lab)",                   13,  3, "Lab"),
            ("Embedded Systems (LEC)",                   13,  1, "Lecture Hall"),
            ("Embedded Systems (Lab)",                   13,  3, "Lab"),
            ("Psychology (LEC)",                         14,  1, "Lecture Hall"),
            ("Neural Networks (LEC)",                    15,  1, "Lecture Hall"),
            ("Neural Networks (TUT)",                    15,  2, "Standard"),
            ("Distributed and Collaborative AI (LEC)",   16,  1, "Lecture Hall"),
            ("Distributed and Collaborative AI (Lab)",   16,  3, "Lab"),
            ("Operational Research 2 (LEC)",             17,  1, "Lecture Hall"),
            ("Operational Research 2 (TUT)",             17,  2, "Standard"),
            ("Time Series Analysis (LEC)",               18,  1, "Lecture Hall"),
            ("Time Series Analysis (TUT)",               18,  2, "Standard"),
            ("Distributed Systems (LEC)",                19,  1, "Lecture Hall"),
            ("Distributed Systems (Project)",            19,  3, "Lab"),
            ("Digital Control Systems (LEC)",            20,  1, "Lecture Hall"),
            ("Digital Control Systems (Lab)",            20,  3, "Lab"),
            ("Power Electronics (LEC)",                  22,  1, "Lecture Hall"),
            ("Power Electronics (Lab)",                  22,  3, "Lab"),
            ("Digital Arts (Lab)",                       21,  2, "Lab"),
            ("Soft Skills (LEC)",                        23,  1, "Lecture Hall"),
        ]
        for name, t_id, g_id, room_type in courses:
            insert_course(name, t_id, g_id, room_type)
        counts["courses"] = len(courses)
        print(f"[Utils] {len(courses)} courses loaded.")
    else:
        print("[Utils] Courses already exist — skipping.")

    print(f"[Utils] HIDE data load complete: {counts}")
    return counts


def export_schedule_csv(schedule, filepath="schedule.csv"):
    """Export schedule to CSV. Returns absolute path."""
    if not schedule:
        print("[Utils] Nothing to export — schedule is empty.")
        return None

    parent = os.path.dirname(os.path.abspath(filepath))
    if parent:
        os.makedirs(parent, exist_ok=True)

    fieldnames = [
        "session_id", "day", "time_slot", "course_name",
        "teacher_name", "group_program", "group_year",
        "room_id", "room_capacity", "equipment",
    ]

    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(schedule)

    abs_path = os.path.abspath(filepath)
    print(f"[Utils] Schedule exported to '{abs_path}' ({len(schedule)} sessions).")
    return abs_path


def format_timetable(schedule):
    """Convert flat schedule list to { day: { slot: [sessions] } } dict."""
    timetable = {day: {slot: [] for slot in TIME_SLOTS} for day in DAYS}
    for session in schedule:
        day  = session.get("day")
        slot = session.get("time_slot")
        if day in timetable and slot in timetable[day]:
            timetable[day][slot].append(session)
    return timetable


def print_schedule(schedule):
    """Pretty-print the full timetable to console."""
    if not schedule:
        print("[Utils] Schedule is empty — nothing to display.")
        return

    timetable = format_timetable(schedule)

    print("\n" + "=" * 80)
    print("  HIDE — PI-2B TIMETABLE")
    print("=" * 80)

    for day in DAYS:
        has_sessions = any(timetable[day][slot] for slot in TIME_SLOTS)
        if not has_sessions:
            continue

        print(f"\n  {day.upper()}")
        print("-" * 80)

        for slot in TIME_SLOTS:
            sessions = timetable[day][slot]
            if not sessions:
                continue
            print(f"  {slot}")
            for s in sessions:
                print(
                    f"      * {s['course_name']}"
                    f" | {s['teacher_name']}"
                    f" | {s['group_program']} Y{s['group_year']}"
                    f" | Room {s['room_id']} (cap. {s['room_capacity']})"
                )

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    load_sample_data()
