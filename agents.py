"""
agents.py - Agent definitions for University Timetabling MAS

Agent hierarchy
---------------
  TeacherAgent    — tracks teacher availability and preferred time slots
  GroupAgent      — tracks student group availability
  RoomAgent       — tracks classroom availability, capacity, and equipment
  ConstraintAgent — validates proposals against hard institutional rules
  SchedulerAgent  — first-fit scheduler; base class for NegotiatingSchedulerAgent
  InterfaceAgent  — read-only gateway to the DB for the web layer

NegotiatingSchedulerAgent (bottom of file) extends SchedulerAgent with:
  - ML-ranked slot ordering  (PreferenceModel)
  - Nash Bargaining Solution (negotiation.py)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mesa import Agent

from config import DAYS, TIME_SLOTS
from database import insert_session, get_schedule

if TYPE_CHECKING:
    from model import TimetablingModel

# Type alias for the availability calendar
Calendar = dict[str, dict[str, bool]]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _empty_calendar() -> Calendar:
    """Return a blank calendar — every slot is free (True)."""
    return {day: {slot: True for slot in TIME_SLOTS} for day in DAYS}


def _calendar_with_unavailable_days(available_days: list[str]) -> Calendar:
    """
    Build a calendar where days NOT in available_days are pre-blocked (False).
    """
    cal = _empty_calendar()
    for day in DAYS:
        if day not in available_days:
            for slot in TIME_SLOTS:
                cal[day][slot] = False
    return cal


# ─────────────────────────────────────────────────────────────────────────────
# TeacherAgent
# ─────────────────────────────────────────────────────────────────────────────

class TeacherAgent(Agent):
    """
    Represents a university teacher.

    Attributes
    ----------
    teacher_id     : int
    name           : str
    available_days : list[str]
    preferred_time : str   "Morning" | "Afternoon"
    preferred_slots: list[str]  pre-computed preferred slot strings
    calendar       : Calendar   per-day/per-slot booking status
    """

    def __init__(self, model: TimetablingModel, teacher_data: dict):
        super().__init__(model)
        self.teacher_id     = teacher_data["teacher_id"]
        self.name           = teacher_data["name"]
        self.available_days = [d.strip() for d in teacher_data["available_days"].split(",")]
        self.preferred_time = teacher_data["preferred_time"]
        self.calendar       = _calendar_with_unavailable_days(self.available_days)
        self.preferred_slots = (
            TIME_SLOTS[:3] if self.preferred_time == "Morning" else TIME_SLOTS[2:]
        )

    # ── Availability ──────────────────────────────────────────────────────────

    def is_available(self, day: str, time_slot: str) -> bool:
        return self.calendar.get(day, {}).get(time_slot, False)

    def sessions_on_day(self, day: str) -> int:
        """Number of already-booked sessions on a given day."""
        return sum(
            1 for slot in TIME_SLOTS
            if not self.calendar.get(day, {}).get(slot, True)
        )

    # ── Booking ───────────────────────────────────────────────────────────────

    def book_slot(self, day: str, time_slot: str) -> bool:
        """
        Mark (day, time_slot) as booked.
        Returns True on success, False if the slot was already taken.
        """
        if not self.is_available(day, time_slot):
            return False
        self.calendar[day][time_slot] = False
        print(f"  [TeacherAgent] {self.name} booked {day} {time_slot}")
        return True

    def step(self) -> None:
        pass   # passive — driven by SchedulerAgent


# ─────────────────────────────────────────────────────────────────────────────
# GroupAgent
# ─────────────────────────────────────────────────────────────────────────────

class GroupAgent(Agent):
    """
    Represents a student group.

    Attributes
    ----------
    group_id   : int
    program    : str
    year       : int
    group_size : int
    calendar   : Calendar   all slots start as free
    """

    def __init__(self, model: TimetablingModel, group_data: dict):
        super().__init__(model)
        self.group_id   = group_data["group_id"]
        self.program    = group_data["program"]
        self.year       = group_data["year"]
        self.group_size = group_data["group_size"]
        self.calendar   = _empty_calendar()   # groups are available every day

    # ── Availability ──────────────────────────────────────────────────────────

    def is_available(self, day: str, time_slot: str) -> bool:
        return self.calendar.get(day, {}).get(time_slot, False)

    def sessions_on_day(self, day: str) -> int:
        return sum(
            1 for slot in TIME_SLOTS
            if not self.calendar.get(day, {}).get(slot, True)
        )

    # ── Booking ───────────────────────────────────────────────────────────────

    def book_slot(self, day: str, time_slot: str) -> bool:
        if not self.is_available(day, time_slot):
            return False
        self.calendar[day][time_slot] = False
        print(f"  [GroupAgent] {self.program} Y{self.year} booked {day} {time_slot}")
        return True

    def step(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# RoomAgent
# ─────────────────────────────────────────────────────────────────────────────

class RoomAgent(Agent):
    """
    Represents a classroom.

    Attributes
    ----------
    room_id   : int
    capacity  : int
    equipment : list[str]
    room_type : str   inferred from equipment
    calendar  : Calendar
    """

    def __init__(self, model: TimetablingModel, room_data: dict):
        super().__init__(model)
        self.room_id   = room_data["room_id"]
        self.capacity  = room_data["capacity"]
        self.equipment = [e.strip() for e in room_data["equipment"].split(",")]
        self.room_type = self._infer_room_type()
        self.calendar  = _empty_calendar()

    def _infer_room_type(self) -> str:
        from config import EQUIPMENT_TO_ROOM_TYPE, ROOM_TYPE_STANDARD
        for equip in self.equipment:
            if equip in EQUIPMENT_TO_ROOM_TYPE:
                return EQUIPMENT_TO_ROOM_TYPE[equip]
        return ROOM_TYPE_STANDARD

    # ── Queries ───────────────────────────────────────────────────────────────

    def is_available(self, day: str, time_slot: str) -> bool:
        return self.calendar.get(day, {}).get(time_slot, False)

    def fits_group(self, group_size: int) -> bool:
        return self.capacity >= group_size

    def matches_type(self, required_room_type: str) -> bool:
        return self.room_type == required_room_type

    # ── Booking ───────────────────────────────────────────────────────────────

    def book_slot(self, day: str, time_slot: str) -> bool:
        if not self.is_available(day, time_slot):
            return False
        self.calendar[day][time_slot] = False
        print(f"  [RoomAgent] Room {self.room_id} ({self.room_type}) booked {day} {time_slot}")
        return True

    def step(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# ConstraintAgent
# ─────────────────────────────────────────────────────────────────────────────

class ConstraintAgent(Agent):
    """
    Validates a scheduling proposal against all hard constraints.

    Hard constraints
    ----------------
    1. Teacher available on (day, slot)
    2. Student group free on (day, slot)
    3. Room free on (day, slot)
    4. Room capacity >= group size
    5. Room type matches course requirement
    """

    def __init__(self, model: TimetablingModel):
        super().__init__(model)

    def check_constraints(self, proposal: dict) -> tuple[bool, str]:
        """
        Parameters
        ----------
        proposal : dict with keys:
            course, teacher_agent, group_agent, room_agent, day, time_slot

        Returns
        -------
        (is_valid: bool, reason: str)
        """
        teacher = proposal["teacher_agent"]
        group   = proposal["group_agent"]
        room    = proposal["room_agent"]
        course  = proposal["course"]
        day     = proposal["day"]
        slot    = proposal["time_slot"]

        if not teacher.is_available(day, slot):
            return False, f"Teacher '{teacher.name}' unavailable {day} {slot}"

        if not group.is_available(day, slot):
            return False, f"Group '{group.program} Y{group.year}' busy {day} {slot}"

        if not room.is_available(day, slot):
            return False, f"Room {room.room_id} occupied {day} {slot}"

        if not room.fits_group(group.group_size):
            return False, (
                f"Room {room.room_id} capacity {room.capacity} "
                f"< group size {group.group_size}"
            )

        if not room.matches_type(course["required_room_type"]):
            return False, (
                f"Room type '{room.room_type}' != "
                f"required '{course['required_room_type']}'"
            )

        return True, "OK"

    def step(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# SchedulerAgent  (first-fit baseline)
# ─────────────────────────────────────────────────────────────────────────────

class SchedulerAgent(Agent):
    """
    Orchestrates timetable generation using a preference-ordered first-fit.

    Workflow per course
    -------------------
    1. Pre-filter rooms by type and capacity (O(1) skip).
    2. Iterate days the teacher is actually available.
    3. Try preferred slots before non-preferred slots.
    4. Check teacher + group availability before room (cheapest checks first).
    5. assign_session() commits the proposal to DB and agent calendars.

    Attributes
    ----------
    assigned   : list[dict]   successfully scheduled sessions
    unresolved : list[dict]   courses that could not be scheduled
    """

    def __init__(self, model: TimetablingModel):
        super().__init__(model)
        self.assigned:   list[dict] = []
        self.unresolved: list[dict] = []

    # ── Proposal ──────────────────────────────────────────────────────────────

    def propose_slot(
        self,
        course: dict,
        teacher_agent: TeacherAgent,
        group_agent: GroupAgent,
        room_agents: list[RoomAgent],
    ) -> dict | None:
        """
        Find the first valid (day, slot, room) for a course.

        Pre-filters rooms once to avoid redundant type/capacity checks
        inside the inner loop. Only calls the heavier ConstraintAgent
        for the room availability check (all other checks are inlined).

        Returns a proposal dict if found, else None.
        """
        required_type = course["required_room_type"]
        group_size    = group_agent.group_size

        # Pre-filter once — removes O(n) type/capacity checks from inner loop
        eligible_rooms = [
            r for r in room_agents
            if r.matches_type(required_type) and r.fits_group(group_size)
        ]
        if not eligible_rooms:
            print(
                f"  [SchedulerAgent] No eligible room for "
                f"'{course['course_name']}' (type={required_type}, size={group_size})"
            )
            return None

        # Preferred slots first, then the rest
        ordered_slots = (
            [s for s in teacher_agent.preferred_slots if s in TIME_SLOTS]
            + [s for s in TIME_SLOTS if s not in teacher_agent.preferred_slots]
        )

        for day in teacher_agent.available_days:
            for slot in ordered_slots:
                # Cheapest availability checks inlined before room loop
                if not teacher_agent.is_available(day, slot):
                    continue
                if not group_agent.is_available(day, slot):
                    continue
                for room in eligible_rooms:
                    if room.is_available(day, slot):
                        return {
                            "course":        course,
                            "teacher_agent": teacher_agent,
                            "group_agent":   group_agent,
                            "room_agent":    room,
                            "day":           day,
                            "time_slot":     slot,
                        }
        return None

    # ── Assignment ────────────────────────────────────────────────────────────

    def assign_session(self, proposal: dict) -> int:
        """
        Commit a validated proposal:
          - Book teacher, group, and room calendars.
          - Persist the session to the database.
          - Record in self.assigned.

        Returns the new session_id.
        """
        teacher = proposal["teacher_agent"]
        group   = proposal["group_agent"]
        room    = proposal["room_agent"]
        day     = proposal["day"]
        slot    = proposal["time_slot"]
        course  = proposal["course"]

        teacher.book_slot(day, slot)
        group.book_slot(day, slot)
        room.book_slot(day, slot)

        session_id = insert_session(course["course_id"], room.room_id, day, slot)

        record = {
            "session_id":  session_id,
            "course_id":   course["course_id"],
            "course_name": course["course_name"],
            "teacher":     teacher.name,
            "group":       f"{group.program} Y{group.year}",
            "room_id":     room.room_id,
            "day":         day,
            "time_slot":   slot,
        }
        self.assigned.append(record)
        print(
            f"  [SchedulerAgent] '{course['course_name']}' → "
            f"{day} {slot} Room {room.room_id}"
        )
        return session_id

    # ── Conflict resolution ───────────────────────────────────────────────────

    def resolve_conflict(self, course: dict) -> None:
        """Log and record an unscheduled course."""
        print(
            f"  [SchedulerAgent] CONFLICT — could not schedule "
            f"'{course['course_name']}' (id={course['course_id']})"
        )
        self.unresolved.append(course)

    # ── Mesa step ─────────────────────────────────────────────────────────────

    def step(self) -> None:
        """Schedule every course in the model."""
        print("\n[SchedulerAgent] Starting scheduling step...")
        for course in self.model.courses:
            teacher_agent = self.model.teacher_map.get(course["teacher_id"])
            group_agent   = self.model.group_map.get(course["group_id"])

            if teacher_agent is None or group_agent is None:
                print(
                    f"  [SchedulerAgent] Missing agent for "
                    f"'{course['course_name']}' — skipping."
                )
                self.unresolved.append(course)
                continue

            proposal = self.propose_slot(
                course, teacher_agent, group_agent, self.model.room_agents
            )

            if proposal:
                self.assign_session(proposal)
            else:
                self.resolve_conflict(course)

        print(
            f"[SchedulerAgent] Done. "
            f"Scheduled: {len(self.assigned)} | "
            f"Unresolved: {len(self.unresolved)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# InterfaceAgent
# ─────────────────────────────────────────────────────────────────────────────

class InterfaceAgent(Agent):
    """
    Read-only gateway between the MAS and the web layer.

    Methods
    -------
    get_timetable() — fetch schedule from DB
    get_summary()   — high-level statistics
    """

    def __init__(self, model: TimetablingModel):
        super().__init__(model)

    def get_timetable(self) -> list[dict]:
        schedule = get_schedule()
        print(f"[InterfaceAgent] Timetable fetched: {len(schedule)} session(s).")
        return schedule

    def get_summary(self) -> dict:
        scheduler = self.model.scheduler_agent
        return {
            "total_courses":   len(self.model.courses),
            "scheduled":       len(scheduler.assigned),
            "unresolved":      len(scheduler.unresolved),
            "unresolved_list": [c["course_name"] for c in scheduler.unresolved],
        }

    def step(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# NegotiatingSchedulerAgent  (Nash Bargaining + ML)
# ─────────────────────────────────────────────────────────────────────────────

class NegotiatingSchedulerAgent(SchedulerAgent):
    """
    Drop-in replacement for SchedulerAgent that combines:
      1. PreferenceModel  — ML-ranked slot ordering per teacher
      2. Nash Bargaining  — picks the slot maximising all agents' utility

    Falls back to the parent first-fit if neither produces a result.

    Extra attributes
    ----------------
    preference_model : PreferenceModel
    negotiation_log  : list[dict]   per-course negotiation details
    ml_used          : int          sessions where ML model was actually used
    fallback_used    : int          sessions where heuristic fallback was used
    """

    def __init__(self, model: TimetablingModel, preference_model):
        super().__init__(model)
        self.preference_model = preference_model
        self.negotiation_log:  list[dict] = []
        self.ml_used:    int = 0
        self.fallback_used: int = 0

    def propose_slot(
        self,
        course: dict,
        teacher_agent: TeacherAgent,
        group_agent: GroupAgent,
        room_agents: list[RoomAgent],
    ) -> dict | None:
        """
        Override: ML preference ranking + Nash negotiation.

        Algorithm
        ---------
        1. Pre-filter rooms (same as parent).
        2. PreferenceModel ranks all free (day, slot) pairs for this teacher.
        3. For each ranked (day, slot), evaluate eligible rooms and compute
           a blended score: Nash-product × (ML_BLEND * ml_score + NASH_BLEND).
        4. Return the proposal with the highest blended score.
        5. Fallback to parent first-fit if nothing found.
        """
        from negotiation import teacher_utility, group_utility, room_utility, nash_product
        from config import ML_W

        required_type = course["required_room_type"]
        group_size    = group_agent.group_size

        eligible_rooms = [
            r for r in room_agents
            if r.matches_type(required_type) and r.fits_group(group_size)
        ]
        if not eligible_rooms:
            return None

        # sessions already booked per day for this teacher
        booked_per_day = {
            day: teacher_agent.sessions_on_day(day) for day in DAYS
        }

        ranked_slots = self.preference_model.rank_slots(
            teacher_agent, course, group_size, booked_per_day
        )

        if ranked_slots:
            best_proposal   = None
            best_score      = -1.0

            for day, slot, ml_score in ranked_slots:
                # Quick inlined pre-checks before computing utilities
                if not teacher_agent.is_available(day, slot):
                    continue
                if not group_agent.is_available(day, slot):
                    continue

                for room in eligible_rooms:
                    if not room.is_available(day, slot):
                        continue

                    u_t = teacher_utility(teacher_agent, day, slot)
                    u_g = group_utility(group_agent, day, slot)
                    u_r = room_utility(room, group_size, day, slot)

                    # Blended score: Nash product weighted by ML preference
                    raw_nash = nash_product([u_t, u_g, u_r])
                    blended  = raw_nash * (ML_W.NASH_BLEND + ML_W.ML_BLEND * ml_score)

                    if blended > best_score:
                        best_score = blended
                        best_proposal = {
                            "course":        course,
                            "teacher_agent": teacher_agent,
                            "group_agent":   group_agent,
                            "room_agent":    room,
                            "day":           day,
                            "time_slot":     slot,
                            "nash_score":    round(raw_nash, 6),
                            "ml_score":      round(ml_score, 4),
                            "utilities":     {"teacher": u_t, "group": u_g, "room": u_r},
                        }

            if best_proposal:
                self.ml_used += 1
                self.negotiation_log.append({
                    "course":    course["course_name"],
                    "day":       best_proposal["day"],
                    "time_slot": best_proposal["time_slot"],
                    "nash_score": best_proposal["nash_score"],
                    "ml_score":   best_proposal["ml_score"],
                })
                print(
                    f"  [NegotiatingScheduler] '{course['course_name']}' → "
                    f"{best_proposal['day']} {best_proposal['time_slot']} "
                    f"Nash={best_proposal['nash_score']:.4f} "
                    f"ML={best_proposal['ml_score']:.4f}"
                )
                return best_proposal

        # Fallback
        print(
            f"  [NegotiatingScheduler] Falling back to first-fit "
            f"for '{course['course_name']}'"
        )
        self.fallback_used += 1
        return super().propose_slot(course, teacher_agent, group_agent, room_agents)

    def get_negotiation_summary(self) -> dict:
        if not self.negotiation_log:
            return {
                "count": 0, "avg_nash": 0.0, "avg_ml": 0.0,
                "ml_used": self.ml_used, "fallback_used": self.fallback_used,
                "log": [],
            }
        avg_nash = sum(r["nash_score"] for r in self.negotiation_log) / len(self.negotiation_log)
        avg_ml   = sum(r["ml_score"]   for r in self.negotiation_log) / len(self.negotiation_log)
        return {
            "count":        len(self.negotiation_log),
            "avg_nash":     round(avg_nash, 4),
            "avg_ml":       round(avg_ml, 4),
            "ml_used":      self.ml_used,
            "fallback_used": self.fallback_used,
            "log":          self.negotiation_log,
        }
