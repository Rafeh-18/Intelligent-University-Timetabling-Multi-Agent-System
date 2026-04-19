"""
model.py - Mesa Model for University Timetabling MAS

TimetablingModel orchestrates all agents and runs the simulation.

Execution order per step
-------------------------
1. SchedulerAgent  — schedules all courses (drives Teacher/Group/Room agents)
2. InterfaceAgent  — exposes results to the web layer
"""

from __future__ import annotations

from mesa import Model

from agents import (
    TeacherAgent,
    GroupAgent,
    RoomAgent,
    SchedulerAgent,
    ConstraintAgent,
    InterfaceAgent,
    NegotiatingSchedulerAgent,
)
from preference_model import PreferenceModel, seed_synthetic_history


class TimetablingModel(Model):
    """
    Central Mesa model for the University Timetabling MAS.

    Parameters
    ----------
    teachers        : list[dict]
    groups          : list[dict]
    classrooms      : list[dict]
    courses         : list[dict]
    use_negotiation : bool (default True) — use Nash + ML scheduler
    """

    def __init__(
        self,
        teachers:   list[dict],
        groups:     list[dict],
        classrooms: list[dict],
        courses:    list[dict],
        use_negotiation: bool = True,
    ):
        super().__init__()

        self.courses         = courses
        self._step_count     = 0
        self.use_negotiation = use_negotiation

        # ── Constraint agent ──────────────────────────────────────────────────
        self.constraint_agent = ConstraintAgent(self)

        # ── Teacher agents ────────────────────────────────────────────────────
        self.teacher_map: dict[int, TeacherAgent] = {}
        for t in teachers:
            agent = TeacherAgent(self, t)
            self.teacher_map[t["teacher_id"]] = agent

        # ── Group agents ──────────────────────────────────────────────────────
        self.group_map: dict[int, GroupAgent] = {}
        for g in groups:
            agent = GroupAgent(self, g)
            self.group_map[g["group_id"]] = agent

        # ── Room agents ───────────────────────────────────────────────────────
        self.room_agents: list[RoomAgent] = []
        for r in classrooms:
            agent = RoomAgent(self, r)
            self.room_agents.append(agent)

        # ── Preference model (ML) ─────────────────────────────────────────────
        self.preference_model = PreferenceModel()
        if use_negotiation:
            # seed_synthetic_history is idempotent — safe to call every run
            seed_synthetic_history(teachers)
            self.preference_model.train()

        # ── Scheduler agent ───────────────────────────────────────────────────
        if use_negotiation:
            self.scheduler_agent: SchedulerAgent = NegotiatingSchedulerAgent(
                self, self.preference_model
            )
            print("[Model] Using NegotiatingSchedulerAgent (Nash + ML)")
        else:
            self.scheduler_agent = SchedulerAgent(self)
            print("[Model] Using basic SchedulerAgent (first-fit)")

        # ── Interface agent ───────────────────────────────────────────────────
        self.interface_agent = InterfaceAgent(self)

        print(
            f"[Model] Initialized — "
            f"{len(teachers)} teachers, {len(groups)} groups, "
            f"{len(classrooms)} classrooms, {len(courses)} courses."
        )

    def step(self) -> None:
        """Run one simulation step (schedule all courses)."""
        self._step_count += 1
        print(f"\n[Model] === Step {self._step_count} ===")
        self.scheduler_agent.step()
        self.interface_agent.step()

    def get_results(self) -> dict:
        """
        Return timetable, summary, negotiation log, and step count.
        """
        timetable   = self.interface_agent.get_timetable()
        summary     = self.interface_agent.get_summary()
        neg_summary = {}

        if (
            self.use_negotiation
            and hasattr(self.scheduler_agent, "get_negotiation_summary")
        ):
            neg_summary = self.scheduler_agent.get_negotiation_summary()

        print(
            f"[Model] Results — "
            f"{summary['scheduled']} scheduled, "
            f"{summary['unresolved']} unresolved."
        )
        if neg_summary:
            print(
                f"[Model] Negotiation — "
                f"avg Nash={neg_summary.get('avg_nash', 0):.4f}  "
                f"avg ML={neg_summary.get('avg_ml', 0):.4f}  "
                f"ML used={neg_summary.get('ml_used', 0)}  "
                f"fallback={neg_summary.get('fallback_used', 0)}"
            )

        return {
            "timetable":   timetable,
            "summary":     summary,
            "negotiation": neg_summary,
            "steps_run":   self._step_count,
        }
