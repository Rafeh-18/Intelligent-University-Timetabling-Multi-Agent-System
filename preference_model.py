"""
preference_model.py - ML Teacher Preference Prediction

Trains one RandomForestClassifier per teacher to predict which (day, slot)
the teacher is most likely to accept, based on historical scheduling data.

When no historical data exists (first run), falls back to the heuristic
day/slot scores defined in config.py.

Features
--------
day_encoded        int   Monday=0 … Saturday=5
slot_index         int   index into TIME_SLOTS
course_type_int    int   Standard=0, Lab=1, Lecture Hall=2
group_size         int
already_booked_day int   how many sessions the teacher already has that day

Label
-----
accepted  1 = slot was assigned historically, 0 = rejected/skipped

History persistence
-------------------
Stored as JSON at HISTORY_FILE (config.py). Each teacher has a key equal to
their teacher_id (as a string). History is seeded once per teacher and never
duplicated on subsequent runs (idempotent).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

from config import (
    DAYS,
    TIME_SLOTS,
    HISTORY_FILE,
    ML_CFG,
    HEURISTIC_DAY_SCORES,
    HEURISTIC_SLOT_SCORES,
)

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[PreferenceModel] scikit-learn not installed — using heuristic fallback.")


# ─────────────────────────────────────────────────────────────────────────────
# Feature encoding
# ─────────────────────────────────────────────────────────────────────────────

_ROOM_TYPE_ENCODING = {"Standard": 0, "Lab": 1, "Lecture Hall": 2}


def encode_features(
    day: str,
    time_slot: str,
    course: dict,
    group_size: int,
    booked_today: int,
) -> list[float]:
    """
    Convert a scheduling proposal into a numeric feature vector.
    Returns [day_idx, slot_idx, room_type_int, group_size, booked_today].
    """
    day_idx       = DAYS.index(day)       if day       in DAYS       else 0
    slot_idx      = TIME_SLOTS.index(time_slot) if time_slot in TIME_SLOTS else 0
    room_type_int = _ROOM_TYPE_ENCODING.get(
        course.get("required_room_type", "Standard"), 0
    )
    return [day_idx, slot_idx, room_type_int, group_size, booked_today]


# ─────────────────────────────────────────────────────────────────────────────
# History persistence
# ─────────────────────────────────────────────────────────────────────────────

def load_history() -> dict:
    """
    Load teacher preference history from HISTORY_FILE.
    Returns dict { teacher_id_str -> list[record_dict] }.
    """
    path = Path(HISTORY_FILE)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[PreferenceModel] Warning: could not read history file: {exc}")
        return {}


def save_history(history: dict) -> None:
    """Persist history dict to HISTORY_FILE."""
    path = Path(HISTORY_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def record_assignment(
    teacher_id: int,
    day: str,
    time_slot: str,
    course: dict,
    group_size: int,
    booked_today: int,
    accepted: int = 1,
) -> None:
    """
    Append a single scheduling outcome to the history file.

    Parameters
    ----------
    accepted : 1 = assigned, 0 = rejected/skipped
    """
    history = load_history()
    key     = str(teacher_id)
    history.setdefault(key, []).append({
        "day":          day,
        "time_slot":    time_slot,
        "course_type":  course.get("required_room_type", "Standard"),
        "group_size":   group_size,
        "booked_today": booked_today,
        "accepted":     accepted,
    })
    save_history(history)


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic history seeding (idempotent)
# ─────────────────────────────────────────────────────────────────────────────

def seed_synthetic_history(
    teachers: list[dict],
    num_records: int = ML_CFG.SEED_RECORDS_PER_TEACHER,
    force: bool = False,
) -> None:
    """
    Generate synthetic scheduling history for teachers that have no records.

    Idempotent: calling this multiple times does NOT append duplicate data.
    Each teacher gets exactly `num_records` records, generated deterministically
    from their teacher_id as the random seed.

    Parameters
    ----------
    teachers   : list of teacher dicts from the database
    num_records: records to generate per teacher (default from ML_CFG)
    force      : if True, overwrite existing records for all teachers
    """
    history = load_history()
    newly_seeded = 0

    for t in teachers:
        key = str(t["teacher_id"])

        # Skip if already has enough records (and not forcing)
        if not force and key in history and len(history[key]) >= num_records:
            continue

        rng    = random.Random(t["teacher_id"])   # deterministic per teacher
        avail  = [d.strip() for d in t["available_days"].split(",")]
        pref   = t["preferred_time"]
        pref_slots  = TIME_SLOTS[:3] if pref == "Morning" else TIME_SLOTS[2:]
        other_slots = [s for s in TIME_SLOTS if s not in pref_slots]

        records: list[dict] = []
        for _ in range(num_records):
            day  = rng.choice(avail)
            slot = (
                rng.choice(pref_slots)
                if rng.random() < ML_CFG.PREFERRED_SLOT_PROBABILITY
                else rng.choice(other_slots)
            )
            accepted = (
                1 if slot in pref_slots
                else int(rng.random() < ML_CFG.NON_PREFERRED_ACCEPT_RATE)
            )
            records.append({
                "day":          day,
                "time_slot":    slot,
                "course_type":  rng.choice(["Standard", "Lab", "Lecture Hall"]),
                "group_size":   rng.randint(16, 32),
                "booked_today": rng.randint(0, 2),
                "accepted":     accepted,
            })

        history[key] = records
        newly_seeded += 1

    if newly_seeded:
        save_history(history)
        print(f"[PreferenceModel] Seeded history for {newly_seeded} teacher(s).")
    else:
        print("[PreferenceModel] All teachers already have history — skipping seed.")


# ─────────────────────────────────────────────────────────────────────────────
# PreferenceModel
# ─────────────────────────────────────────────────────────────────────────────

class PreferenceModel:
    """
    Per-teacher preference predictor.

    Usage
    -----
    pm = PreferenceModel()
    pm.train()
    ranked = pm.rank_slots(teacher_agent, course, group_size, booked_per_day)

    Observability
    -------------
    After training, `trained_teacher_ids` contains the IDs of teachers
    for which an ML model was successfully fitted. All others use the
    heuristic fallback, which is logged during prediction.
    """

    def __init__(self):
        self._models: dict[str, "RandomForestClassifier"] = {}
        self.trained_teacher_ids: set[str] = set()

    def train(self) -> None:
        """
        Train one RandomForestClassifier per teacher using stored history.
        Teachers with fewer than ML_CFG.MIN_RECORDS_TO_TRAIN records are
        skipped (heuristic fallback will be used for them).
        """
        if not SKLEARN_AVAILABLE:
            print("[PreferenceModel] Cannot train — scikit-learn unavailable.")
            return

        history = load_history()
        trained = 0
        skipped = 0

        for teacher_id, records in history.items():
            if len(records) < ML_CFG.MIN_RECORDS_TO_TRAIN:
                skipped += 1
                continue

            X = []
            y = []
            for r in records:
                course_stub = {"required_room_type": r.get("course_type", "Standard")}
                X.append(encode_features(
                    r["day"], r["time_slot"], course_stub,
                    r["group_size"], r.get("booked_today", 0),
                ))
                y.append(r["accepted"])

            X_arr = np.array(X)
            y_arr = np.array(y)

            # Need at least two classes to train a classifier
            if len(set(y_arr)) < 2:
                skipped += 1
                continue

            clf = RandomForestClassifier(
                n_estimators=ML_CFG.N_ESTIMATORS,
                max_depth=ML_CFG.MAX_DEPTH,
                random_state=ML_CFG.RANDOM_STATE,
                class_weight="balanced",
            )

            if len(X_arr) >= ML_CFG.VAL_SPLIT_THRESHOLD:
                X_tr, X_val, y_tr, y_val = train_test_split(
                    X_arr, y_arr,
                    test_size=ML_CFG.VAL_SPLIT_RATIO,
                    random_state=ML_CFG.RANDOM_STATE,
                    stratify=y_arr,
                )
                clf.fit(X_tr, y_tr)
                acc = clf.score(X_val, y_val)
                print(
                    f"  [PreferenceModel] Teacher {teacher_id}: "
                    f"n={len(X_tr)} val_acc={acc:.2f}"
                )
            else:
                clf.fit(X_arr, y_arr)
                print(
                    f"  [PreferenceModel] Teacher {teacher_id}: "
                    f"n={len(X_arr)} (no val split)"
                )

            self._models[teacher_id] = clf
            self.trained_teacher_ids.add(teacher_id)
            trained += 1

        print(
            f"[PreferenceModel] Training complete — "
            f"{trained} ML models ready, {skipped} using heuristic fallback."
        )

    def predict_acceptance(
        self,
        teacher_id: int,
        day: str,
        time_slot: str,
        course: dict,
        group_size: int,
        booked_today: int,
    ) -> float:
        """
        Predict P(teacher accepts (day, slot)).

        Returns float in [0.0, 1.0].
        Uses ML model when available; logs whether ML or heuristic was used.
        """
        key = str(teacher_id)

        if SKLEARN_AVAILABLE and key in self._models:
            features = encode_features(day, time_slot, course, group_size, booked_today)
            proba    = self._models[key].predict_proba([features])[0]
            classes  = list(self._models[key].classes_)
            return float(proba[classes.index(1)]) if 1 in classes else 0.5

        # Heuristic fallback
        return self._heuristic_score(day, time_slot)

    def _heuristic_score(self, day: str, time_slot: str) -> float:
        """
        Simple day × slot heuristic. Used when no ML model exists.
        Scores are defined in config.HEURISTIC_DAY_SCORES and
        config.HEURISTIC_SLOT_SCORES.
        """
        d = HEURISTIC_DAY_SCORES.get(day, 0.5)
        s = HEURISTIC_SLOT_SCORES.get(time_slot, 0.5)
        return round((d + s) / 2, 4)

    def rank_slots(
        self,
        teacher_agent,
        course: dict,
        group_size: int,
        booked_per_day: dict[str, int],
    ) -> list[tuple[str, str, float]]:
        """
        Rank all free (day, slot) pairs for a teacher by predicted acceptance.

        Parameters
        ----------
        teacher_agent  : TeacherAgent
        course         : dict
        group_size     : int
        booked_per_day : { day -> sessions_already_booked }

        Returns
        -------
        list[(day, slot, score)] sorted highest-score first.
        Only includes slots where teacher is currently available.
        """
        ranked: list[tuple[str, str, float]] = []

        for day in teacher_agent.available_days:
            booked_today = booked_per_day.get(day, 0)
            for slot in TIME_SLOTS:
                if not teacher_agent.is_available(day, slot):
                    continue
                score = self.predict_acceptance(
                    teacher_agent.teacher_id,
                    day, slot, course, group_size, booked_today,
                )
                ranked.append((day, slot, score))

        ranked.sort(key=lambda x: x[2], reverse=True)
        return ranked
