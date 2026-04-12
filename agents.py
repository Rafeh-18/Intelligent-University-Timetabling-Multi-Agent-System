"""
agents.py - Agent definitions for University Timetabling MAS

Agent hierarchy:
  TeacherAgent    — tracks teacher availability and preferred time slots
  GroupAgent      — tracks student group availability
  RoomAgent       — tracks classroom availability and capacity/equipment
  SchedulerAgent  — orchestrates scheduling: proposes, negotiates, assigns
  ConstraintAgent — validates proposals against institutional rules
  InterfaceAgent  — exposes the final timetable to the web layer
"""

from mesa import Agent
from utils import DAYS, TIME_SLOTS
from database import insert_session, get_schedule


# ── Helpers ───────────────────────────────────────────────────────────────────

def _empty_calendar():
    """Return a blank availability calendar: all slots free (True)."""
    return {day: {slot: True for slot in TIME_SLOTS} for day in DAYS}


# ─────────────────────────────────────────────────────────────────────────────
# TeacherAgent
# ─────────────────────────────────────────────────────────────────────────────

class TeacherAgent(Agent):
    """
    Represents a university teacher.

    Attributes
    ----------
    teacher_id      : int
    name            : str
    available_days  : list[str]   days the teacher is available
    preferred_time  : str         "Morning" or "Afternoon"
    calendar        : dict        per-day/per-slot booking status
    """

    def __init__(self, model, teacher_data):
        super().__init__(model)
        self.teacher_id     = teacher_data["teacher_id"]
        self.name           = teacher_data["name"]
        self.available_days = [d.strip() for d in teacher_data["available_days"].split(",")]
        self.preferred_time = teacher_data["preferred_time"]
        self.calendar       = _empty_calendar()

        # Mark days the teacher is NOT available as already booked
        for day in DAYS:
            if day not in self.available_days:
                for slot in TIME_SLOTS:
                    self.calendar[day][slot] = False

        # Soft-preference: de-prioritise off-preference slots (still usable)
        self.preferred_slots = (
            TIME_SLOTS[:3] if self.preferred_time == "Morning" else TIME_SLOTS[2:]
        )

    def is_available(self, day, time_slot):
        """Return True if the teacher is free on (day, time_slot)."""
        return self.calendar.get(day, {}).get(time_slot, False)

    def book_slot(self, day, time_slot):
        """
        Mark (day, time_slot) as booked.
        Returns True on success, False if the slot was already taken.
        """
        if not self.is_available(day, time_slot):
            return False
        self.calendar[day][time_slot] = False
        print(f"  [TeacherAgent] {self.name} booked on {day} {time_slot}")
        return True

    def step(self):
        """Mesa step — passive agent; scheduler drives it."""
        pass


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
    calendar   : dict   per-day/per-slot booking status
    """

    def __init__(self, model, group_data):
        super().__init__(model)
        self.group_id   = group_data["group_id"]
        self.program    = group_data["program"]
        self.year       = group_data["year"]
        self.group_size = group_data["group_size"]
        self.calendar   = _empty_calendar()

    def is_available(self, day, time_slot):
        """Return True if the group has no class on (day, time_slot)."""
        return self.calendar.get(day, {}).get(time_slot, False)

    def book_slot(self, day, time_slot):
        """
        Mark (day, time_slot) as occupied for this group.
        Returns True on success, False if already booked.
        """
        if not self.is_available(day, time_slot):
            return False
        self.calendar[day][time_slot] = False
        print(f"  [GroupAgent] {self.program} Y{self.year} booked on {day} {time_slot}")
        return True

    def step(self):
        """Mesa step — passive agent; scheduler drives it."""
        pass


# ─────────────────────────────────────────────────────────────────────────────
# RoomAgent
# ─────────────────────────────────────────────────────────────────────────────

class RoomAgent(Agent):
    """
    Represents a classroom.

    Attributes
    ----------
    room_id    : int
    capacity   : int
    equipment  : list[str]
    room_type  : str    inferred from equipment ("Lab", "Lecture Hall", "Standard")
    calendar   : dict   per-day/per-slot booking status
    """

    def __init__(self, model, room_data):
        super().__init__(model)
        self.room_id   = room_data["room_id"]
        self.capacity  = room_data["capacity"]
        self.equipment = [e.strip() for e in room_data["equipment"].split(",")]
        self.room_type = self._infer_room_type()
        self.calendar  = _empty_calendar()

    def _infer_room_type(self):
        """Derive room type from equipment list."""
        if "Computers" in self.equipment:
            return "Lab"
        if "Microphone" in self.equipment:
            return "Lecture Hall"
        return "Standard"

    def is_available(self, day, time_slot):
        """Return True if the room is free on (day, time_slot)."""
        return self.calendar.get(day, {}).get(time_slot, False)

    def fits_group(self, group_size):
        """Return True if the room can accommodate the group."""
        return self.capacity >= group_size

    def matches_type(self, required_room_type):
        """Return True if the room type satisfies the course requirement."""
        return self.room_type == required_room_type

    def book_slot(self, day, time_slot):
        """
        Mark (day, time_slot) as occupied.
        Returns True on success, False if already booked.
        """
        if not self.is_available(day, time_slot):
            return False
        self.calendar[day][time_slot] = False
        print(f"  [RoomAgent] Room {self.room_id} ({self.room_type}) booked on {day} {time_slot}")
        return True

    def step(self):
        """Mesa step — passive agent; scheduler drives it."""
        pass


# ─────────────────────────────────────────────────────────────────────────────
# ConstraintAgent
# ─────────────────────────────────────────────────────────────────────────────

class ConstraintAgent(Agent):
    """
    Validates a scheduling proposal against all hard constraints.

    Hard constraints checked
    ------------------------
    1. Teacher must be available on the proposed (day, slot).
    2. Student group must be free on the proposed (day, slot).
    3. Room must be free on the proposed (day, slot).
    4. Room capacity must accommodate the group size.
    5. Room type must match the course requirement.
    """

    def __init__(self, model):
        super().__init__(model)

    def check_constraints(self, session_proposal):
        """
        Validate a proposal dict.

        Expected keys
        -------------
        course        : dict   from get_all_courses()
        teacher_agent : TeacherAgent
        group_agent   : GroupAgent
        room_agent    : RoomAgent
        day           : str
        time_slot     : str

        Returns
        -------
        (bool, str)  — (is_valid, reason_if_invalid)
        """
        course   = session_proposal["course"]
        teacher  = session_proposal["teacher_agent"]
        group    = session_proposal["group_agent"]
        room     = session_proposal["room_agent"]
        day      = session_proposal["day"]
        slot     = session_proposal["time_slot"]

        if not teacher.is_available(day, slot):
            return False, f"Teacher '{teacher.name}' unavailable on {day} {slot}"

        if not group.is_available(day, slot):
            return False, f"Group '{group.program} Y{group.year}' busy on {day} {slot}"

        if not room.is_available(day, slot):
            return False, f"Room {room.room_id} occupied on {day} {slot}"

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

    def step(self):
        """Mesa step — called by the model each tick."""
        pass


# ─────────────────────────────────────────────────────────────────────────────
# SchedulerAgent
# ─────────────────────────────────────────────────────────────────────────────

class SchedulerAgent(Agent):
    """
    Orchestrates the timetable generation process.

    Workflow per course
    -------------------
    1. propose_slot()  — iterate days/slots to find a candidate
    2. ConstraintAgent validates the proposal
    3. assign_session() — books all three agents and persists to DB
    4. resolve_conflict() — called when no valid slot is found

    Attributes
    ----------
    assigned   : list[dict]   successfully scheduled sessions
    unresolved : list[dict]   courses that could not be scheduled
    """

    def __init__(self, model):
        super().__init__(model)
        self.assigned   = []
        self.unresolved = []

    def propose_slot(self, course, teacher_agent, group_agent, room_agents):
        """
        Find the first valid (day, time_slot, room_agent) for a course.

        Soft preference: preferred teacher time slots are tried first.
        Returns a proposal dict if found, else None.
        """
        # Build ordered slot list: preferred slots first
        ordered_slots = (
            [s for s in teacher_agent.preferred_slots if s in TIME_SLOTS]
            + [s for s in TIME_SLOTS if s not in teacher_agent.preferred_slots]
        )

        for day in DAYS:
            for slot in ordered_slots:
                for room in room_agents:
                    proposal = {
                        "course":         course,
                        "teacher_agent":  teacher_agent,
                        "group_agent":    group_agent,
                        "room_agent":     room,
                        "day":            day,
                        "time_slot":      slot,
                    }
                    is_valid, reason = self.model.constraint_agent.check_constraints(proposal)
                    if is_valid:
                        return proposal

        return None  # No valid slot found

    def resolve_conflict(self, course):
        """
        Handle courses that could not be scheduled.
        Logs the conflict and adds the course to the unresolved list.
        Returns False to signal the conflict was not resolved.
        """
        print(
            f"  [SchedulerAgent] CONFLICT — could not schedule "
            f"'{course['course_name']}' (id={course['course_id']})"
        )
        self.unresolved.append(course)
        return False

    def assign_session(self, proposal):
        """
        Commit a validated proposal:
          - Book teacher, group, and room calendars
          - Persist the session to the database
          - Record in self.assigned

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
            f"  [SchedulerAgent] Assigned '{course['course_name']}' "
            f"-> {day} {slot} Room {room.room_id}"
        )
        return session_id

    def step(self):
        """
        Mesa step: schedule all unscheduled courses in the model.
        Iterates through every course and tries to assign it.
        """
        print("\n[SchedulerAgent] Starting scheduling step...")
        for course in self.model.courses:
            teacher_agent = self.model.teacher_map.get(course["teacher_id"])
            group_agent   = self.model.group_map.get(course["group_id"])

            if teacher_agent is None or group_agent is None:
                print(f"  [SchedulerAgent] Missing agent for course '{course['course_name']}' — skipping.")
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
    Provides read access to the generated timetable for the web layer.

    Methods
    -------
    get_timetable()  — fetch the full schedule from the DB
    get_summary()    — return high-level statistics
    """

    def __init__(self, model):
        super().__init__(model)

    def get_timetable(self):
        """
        Fetch and return the full schedule from the database.
        Returns a list of dicts (one per session).
        """
        schedule = get_schedule()
        print(f"[InterfaceAgent] Timetable fetched: {len(schedule)} session(s).")
        return schedule

    def get_summary(self):
        """
        Return a summary dict with scheduling statistics.
        """
        scheduler = self.model.scheduler_agent
        return {
            "total_courses":    len(self.model.courses),
            "scheduled":        len(scheduler.assigned),
            "unresolved":       len(scheduler.unresolved),
            "unresolved_list":  [c["course_name"] for c in scheduler.unresolved],
        }

    def step(self):
        """Mesa step — passive agent; called last by the model."""
        pass


# ─────────────────────────────────────────────────────────────────────────────
# NegotiatingSchedulerAgent  (extends SchedulerAgent with game theory + ML)
# ─────────────────────────────────────────────────────────────────────────────

class NegotiatingSchedulerAgent(SchedulerAgent):
    """
    Drop-in replacement for SchedulerAgent that uses:
      1. PreferenceModel  — ML-ranked slot ordering per teacher
      2. negotiate_slot() — Nash Bargaining Solution for final selection

    Falls back to basic first-fit if neither produces a result.

    Extra attributes
    ----------------
    preference_model : PreferenceModel   (trained on historical data)
    negotiation_log  : list[dict]        per-course negotiation details
    """

    def __init__(self, model, preference_model):
        super().__init__(model)
        self.preference_model = preference_model
        self.negotiation_log  = []

    def propose_slot(self, course, teacher_agent, group_agent, room_agents):
        """
        Override: use ML preference ranking + Nash negotiation.

        Step 1 — PreferenceModel ranks all free slots for this teacher.
        Step 2 — Iterate ranked slots and run Nash negotiation.
        Step 3 — Return the proposal with the highest Nash score.
        Step 4 — Fallback to basic first-fit if nothing found.
        """
        from negotiation import negotiate_slot

        # Count sessions already booked per day for this teacher
        booked_per_day = {
            day: sum(
                1 for slot in TIME_SLOTS
                if not teacher_agent.calendar[day][slot]
            )
            for day in DAYS
        }

        # ML-ranked slot ordering
        ranked_slots = self.preference_model.rank_slots(
            teacher_agent, course, group_agent.group_size, booked_per_day
        )

        if ranked_slots:
            # Try Nash negotiation using ML-ranked ordering
            best_proposal   = None
            best_nash_score = -1.0

            for day, slot, ml_score in ranked_slots:
                for room in room_agents:
                    proposal = {
                        "course":        course,
                        "teacher_agent": teacher_agent,
                        "group_agent":   group_agent,
                        "room_agent":    room,
                        "day":           day,
                        "time_slot":     slot,
                    }
                    is_valid, _ = self.model.constraint_agent.check_constraints(proposal)
                    if not is_valid:
                        continue

                    from negotiation import (teacher_utility, group_utility,
                                             room_utility, nash_product)
                    u_t = teacher_utility(teacher_agent, day, slot)
                    u_g = group_utility(group_agent, day, slot)
                    u_r = room_utility(room, group_agent.group_size, day, slot)

                    # Blend ML score into Nash product
                    nash = nash_product([u_t, u_g, u_r]) * (0.7 + 0.3 * ml_score)

                    if nash > best_nash_score:
                        best_nash_score = nash
                        best_proposal   = {
                            **proposal,
                            "nash_score": round(nash, 6),
                            "ml_score":   round(ml_score, 4),
                            "utilities":  {"teacher": u_t, "group": u_g, "room": u_r},
                        }

            if best_proposal:
                self.negotiation_log.append({
                    "course":     course["course_name"],
                    "day":        best_proposal["day"],
                    "time_slot":  best_proposal["time_slot"],
                    "nash_score": best_proposal["nash_score"],
                    "ml_score":   best_proposal["ml_score"],
                })
                print(
                    f"  [NegotiatingScheduler] '{course['course_name']}' → "
                    f"{best_proposal['day']} {best_proposal['time_slot']} "
                    f"Nash={best_proposal['nash_score']:.4f} ML={best_proposal['ml_score']:.4f}"
                )
                return best_proposal

        # Fallback: basic first-fit from parent class
        print(f"  [NegotiatingScheduler] Falling back to first-fit for '{course['course_name']}'")
        return super().propose_slot(course, teacher_agent, group_agent, room_agents)

    def get_negotiation_summary(self):
        """Return a summary of all Nash scores from this scheduling run."""
        if not self.negotiation_log:
            return {"count": 0, "avg_nash": 0.0, "avg_ml": 0.0}
        avg_nash = sum(r["nash_score"] for r in self.negotiation_log) / len(self.negotiation_log)
        avg_ml   = sum(r["ml_score"]   for r in self.negotiation_log) / len(self.negotiation_log)
        return {
            "count":    len(self.negotiation_log),
            "avg_nash": round(avg_nash, 4),
            "avg_ml":   round(avg_ml, 4),
            "log":      self.negotiation_log,
        }