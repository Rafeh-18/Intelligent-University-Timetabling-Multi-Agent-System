"""
agents.py - Agent definitions for University Timetabling MAS
"""

from mesa import Agent


class TeacherAgent(Agent):

    def __init__(self, unique_id, model, teacher_data):
        pass

    def is_available(self, day, time_slot):
        pass

    def book_slot(self, day, time_slot):
        pass

    def step(self):
        pass


class GroupAgent(Agent):

    def __init__(self, unique_id, model, group_data):
        pass

    def is_available(self, day, time_slot):
        pass

    def book_slot(self, day, time_slot):
        pass

    def step(self):
        pass


class RoomAgent(Agent):

    def __init__(self, unique_id, model, room_data):
        pass

    def is_available(self, day, time_slot):
        pass

    def book_slot(self, day, time_slot):
        pass

    def step(self):
        pass


class SchedulerAgent(Agent):

    def __init__(self, unique_id, model):
        pass

    def propose_slot(self, course):
        pass

    def resolve_conflict(self, conflict):
        pass

    def assign_session(self, course, room, day, time_slot):
        pass

    def step(self):
        pass


class ConstraintAgent(Agent):

    def __init__(self, unique_id, model):
        pass

    def check_constraints(self, session_proposal):
        pass

    def step(self):
        pass


class InterfaceAgent(Agent):

    def __init__(self, unique_id, model):
        pass

    def get_timetable(self):
        pass

    def step(self):
        pass
