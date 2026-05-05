"""
config.py - Central configuration for University Timetabling MAS

All magic numbers, weights, paths, and tunable parameters live here.
Change values here to tune the scheduler without touching business logic.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
DB_PATH      = BASE_DIR / "timetable.db"
HISTORY_FILE = BASE_DIR / "preference_history.json"

# ── Days & Slots ──────────────────────────────────────────────────────────────
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# NOTE: No overlapping slots. These strings must exactly match the frontend.
TIME_SLOTS = [
    "08:30-10:00",
    "10:15-11:45",
    "13:00-14:30",
    "14:45-16:15",
    "16:15-18:00",
]

MORNING_SLOTS   = TIME_SLOTS[:3]   # 08:30, 10:15, 12:00
AFTERNOON_SLOTS = TIME_SLOTS[2:]   # 12:00, 14:45, 16:15

# ── Room type inference ───────────────────────────────────────────────────────
ROOM_TYPE_LAB          = "Lab"
ROOM_TYPE_LECTURE_HALL = "Lecture Hall"
ROOM_TYPE_STANDARD     = "Standard"

EQUIPMENT_TO_ROOM_TYPE = {
    "Computers": ROOM_TYPE_LAB,
    "Microphone": ROOM_TYPE_LECTURE_HALL,
}

# ── Negotiation / Utility weights ─────────────────────────────────────────────
@dataclass(frozen=True)
class TeacherWeights:
    BASE_SCORE:            float = 0.4   # slot is free
    PREFERRED_BONUS:       float = 0.6   # slot is in preferred band
    NON_PREFERRED_BONUS:   float = 0.2   # slot outside preferred band but usable
    DAILY_LOAD_PENALTY:    float = 0.15  # per session already booked today
    MAX_DAILY_PENALTY:     float = 0.45  # cap on daily-load penalty

@dataclass(frozen=True)
class GroupWeights:
    BASE_SCORE:   float = 0.5   # slot is free
    SPREAD_BONUS: float = 0.5   # even distribution bonus

@dataclass(frozen=True)
class RoomWeights:
    EFFICIENCY_MULTIPLIER: float = 1.2   # room_size / capacity; capped at 1.0

@dataclass(frozen=True)
class MLWeights:
    NASH_BLEND:  float = 0.7   # weight of pure Nash product
    ML_BLEND:    float = 0.3   # weight of ML preference score

TEACHER_W = TeacherWeights()
GROUP_W   = GroupWeights()
ROOM_W    = RoomWeights()
ML_W      = MLWeights()

# ── Preference model ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class MLConfig:
    N_ESTIMATORS:          int   = 40
    MAX_DEPTH:             int   = 4
    RANDOM_STATE:          int   = 42
    MIN_RECORDS_TO_TRAIN:  int   = 4
    VAL_SPLIT_THRESHOLD:   int   = 8
    VAL_SPLIT_RATIO:       float = 0.25
    SEED_RECORDS_PER_TEACHER: int = 20
    PREFERRED_SLOT_PROBABILITY: float = 0.7
    NON_PREFERRED_ACCEPT_RATE:  float = 0.3

ML_CFG = MLConfig()

# ── Day-of-week heuristic scores (fallback when no ML model) ──────────────────
HEURISTIC_DAY_SCORES = {
    "Monday":    0.7,
    "Tuesday":   0.9,
    "Wednesday": 1.0,
    "Thursday":  0.9,
    "Friday":    0.6,
    "Saturday":  0.5,
}

HEURISTIC_SLOT_SCORES = {
    "08:30-10:00": 0.7,
    "10:15-11:45": 1.0,
    "13:00-14:30": 0.5,
    "14:45-16:15": 0.8,
    "16:15-18:00": 0.6,
}

# ── Flask ─────────────────────────────────────────────────────────────────────
FLASK_PORT     = int(os.environ.get("PORT", 5000))
FLASK_DEBUG    = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
API_TOKEN      = os.environ.get("API_TOKEN", "")   # empty = no auth (dev only)
