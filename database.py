"""
database.py - Database layer for University Timetabling MAS
"""

import sqlite3

DB_PATH = "timetable.db"


def init_db():
    pass


def create_tables():
    pass


def insert_teacher(name, available_days, preferred_time):
    pass


def insert_group(program, year, group_size):
    pass


def insert_classroom(capacity, equipment):
    pass


def insert_course(course_name, teacher_id, group_id, required_room_type):
    pass


def insert_session(course_id, room_id, day, time_slot):
    pass


def get_all_teachers():
    pass


def get_all_groups():
    pass


def get_all_classrooms():
    pass


def get_all_courses():
    pass


def get_schedule():
    pass


def clear_schedule():
    pass
