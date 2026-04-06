"""
model.py - Mesa Model for University Timetabling MAS
"""

from mesa import Model
from mesa.time import RandomActivation
from agents import TeacherAgent, GroupAgent, RoomAgent, SchedulerAgent, ConstraintAgent, InterfaceAgent


class TimetablingModel(Model):

    def __init__(self, teachers, groups, classrooms, courses):
        pass

    def step(self):
        pass

    def get_results(self):
        pass
