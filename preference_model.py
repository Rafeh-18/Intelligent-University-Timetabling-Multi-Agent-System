"""
preference_model.py - ML Teacher Preference Prediction (scikit-learn)

Trains a RandomForestClassifier per teacher to predict which time slot
they are most likely to accept, based on historical scheduling data.

When no historical data exists (first run), the model falls back to
the teacher's declared preferred_time from the database.

Features used
-------------
- day_encoded        : integer encoding of day (Mon=0 … Fri=4)
- slot_index         : integer index of time slot (0–4)
- course_type        : integer encoding of required_room_type
- group_size         : integer (student count)
- already_booked_day : how many sessions the teacher already has that day

Label
-----
- accepted : 1 if the teacher was assigned this slot historically, 0 otherwise
"""

import os
import json
import numpy as np

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[PreferenceModel] scikit-learn not installed — using rule-based fallback.")

from utils import DAYS, TIME_SLOTS

# Where we persist training data between runs
HISTORY_FILE = "preference_history.json"


# ─────────────────────────────────────────────────────────────────────────────
# Feature engineering
# ─────────────────────────────────────────────────────────────────────────────

ROOM_TYPE_MAP = {"Standard": 0, "Lab": 1, "Lecture Hall": 2}

def encode_features(day, time_slot, course, group_size, booked_today):
    """
    Convert a scheduling proposal into a numeric feature vector.

    Returns
    -------
    list[int | float]  [day_idx, slot_idx, room_type_int, group_size, booked_today]
    """
    day_idx       = DAYS.index(day) if day in DAYS else 0
    slot_idx      = TIME_SLOTS.index(time_slot) if time_slot in TIME_SLOTS else 0
    room_type_int = ROOM_TYPE_MAP.get(course.get("required_room_type", "Standard"), 0)
    return [day_idx, slot_idx, room_type_int, group_size, booked_today]


# ─────────────────────────────────────────────────────────────────────────────
# History persistence
# ─────────────────────────────────────────────────────────────────────────────

def load_history():
    """
    Load historical scheduling decisions from HISTORY_FILE.
    Returns dict { teacher_id(str) -> list[dict] }
    """
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def save_history(history):
    """Persist history dict to HISTORY_FILE."""
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def record_assignment(teacher_id, day, time_slot, course, group_size, booked_today, accepted=1):
    """
    Record a scheduling outcome to the history file.

    Parameters
    ----------
    accepted : int  1 = slot was assigned, 0 = slot was rejected/skipped
    """
    history = load_history()
    key     = str(teacher_id)
    if key not in history:
        history[key] = []

    history[key].append({
        "day":          day,
        "time_slot":    time_slot,
        "course_type":  course.get("required_room_type", "Standard"),
        "group_size":   group_size,
        "booked_today": booked_today,
        "accepted":     accepted,
    })

    save_history(history)


# ─────────────────────────────────────────────────────────────────────────────
# PreferenceModel class
# ─────────────────────────────────────────────────────────────────────────────

class PreferenceModel:
    """
    Per-teacher preference predictor.

    Usage
    -----
    pm = PreferenceModel()
    pm.train()                          # train on all available history
    slots = pm.rank_slots(teacher, course, group_size, booked_per_day)
    """

    def __init__(self):
        self._models   = {}   # { teacher_id -> fitted RandomForestClassifier }
        self._trained  = False
        self._history  = {}

    def train(self):
        """
        Train one RandomForestClassifier per teacher using history.
        Falls back gracefully if a teacher has insufficient data (<4 records).
        """
        if not SKLEARN_AVAILABLE:
            print("[PreferenceModel] Skipping training — scikit-learn unavailable.")
            return

        self._history = load_history()
        trained_count = 0

        for teacher_id, records in self._history.items():
            if len(records) < 4:
                # Not enough data to train — will use rule-based fallback
                continue

            X, y = [], []
            for r in records:
                booked = r.get("booked_today", 0)
                course_stub = {"required_room_type": r.get("course_type", "Standard")}
                features = encode_features(
                    r["day"], r["time_slot"], course_stub,
                    r["group_size"], booked
                )
                X.append(features)
                y.append(r["accepted"])

            X = np.array(X)
            y = np.array(y)

            # Need at least two classes to train a classifier
            if len(set(y)) < 2:
                continue

            clf = RandomForestClassifier(
                n_estimators=40,
                max_depth=4,
                random_state=42,
                class_weight="balanced",
            )

            # Only split if we have enough samples
            if len(X) >= 8:
                X_tr, X_val, y_tr, y_val = train_test_split(
                    X, y, test_size=0.25, random_state=42, stratify=y
                )
                clf.fit(X_tr, y_tr)
                acc = clf.score(X_val, y_val)
                print(
                    f"  [PreferenceModel] Teacher {teacher_id}: "
                    f"trained on {len(X_tr)} samples, val acc={acc:.2f}"
                )
            else:
                clf.fit(X, y)
                print(
                    f"  [PreferenceModel] Teacher {teacher_id}: "
                    f"trained on {len(X)} samples (no val split)"
                )

            self._models[teacher_id] = clf
            trained_count += 1

        self._trained = trained_count > 0
        print(
            f"[PreferenceModel] Training complete — "
            f"{trained_count} teacher model(s) ready."
        )

    def predict_acceptance(self, teacher_id, day, time_slot, course, group_size, booked_today):
        """
        Predict the probability that teacher_id will accept (day, time_slot).

        Returns float in [0.0, 1.0].
        Falls back to a heuristic if no model is available.
        """
        key = str(teacher_id)

        if SKLEARN_AVAILABLE and key in self._models:
            features = encode_features(day, time_slot, course, group_size, booked_today)
            prob = self._models[key].predict_proba([features])[0]
            # prob is [P(rejected), P(accepted)] — return P(accepted)
            classes = list(self._models[key].classes_)
            if 1 in classes:
                return float(prob[classes.index(1)])
            return 0.5

        # ── Rule-based fallback ──────────────────────────────────────────────
        return self._rule_based_score(day, time_slot)

    def _rule_based_score(self, day, time_slot):
        """
        Simple heuristic: mid-week morning slots score highest.
        Used when no ML model is trained yet.
        """
        day_scores  = {"Monday": 0.7, "Tuesday": 0.9, "Wednesday": 1.0,
                       "Thursday": 0.9, "Friday": 0.6}
        slot_scores = {
            "08:00-10:00": 0.7,
            "10:00-12:00": 1.0,
            "12:00-14:00": 0.5,
            "14:00-16:00": 0.8,
            "16:00-18:00": 0.6,
        }
        d = day_scores.get(day, 0.5)
        s = slot_scores.get(time_slot, 0.5)
        return round((d + s) / 2, 4)

    def rank_slots(self, teacher_agent, course, group_size, booked_per_day):
        """
        Rank all available (day, slot) pairs for a teacher by predicted acceptance.

        Parameters
        ----------
        teacher_agent : TeacherAgent
        course        : dict
        group_size    : int
        booked_per_day: dict { day -> int }  sessions already booked that day

        Returns
        -------
        list[tuple[str, str, float]]
            Sorted [(day, slot, score), ...] highest first — only free slots.
        """
        ranked = []
        for day in DAYS:
            booked_today = booked_per_day.get(day, 0)
            for slot in TIME_SLOTS:
                if not teacher_agent.is_available(day, slot):
                    continue
                score = self.predict_acceptance(
                    teacher_agent.teacher_id,
                    day, slot, course, group_size, booked_today
                )
                ranked.append((day, slot, score))

        ranked.sort(key=lambda x: x[2], reverse=True)
        return ranked


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: seed synthetic history for demo purposes
# ─────────────────────────────────────────────────────────────────────────────

def seed_synthetic_history(teachers, num_records=20):
    """
    Generate synthetic scheduling history so the ML model has something
    to train on from the very first run.

    Simulates that teachers strongly prefer their declared preferred_time.
    Call this once from utils.load_sample_data() or manually.
    """
    import random
    random.seed(42)

    history = load_history()

    for t in teachers:
        key     = str(t["teacher_id"])
        avail   = [d.strip() for d in t["available_days"].split(",")]
        pref    = t["preferred_time"]
        pref_slots = TIME_SLOTS[:3] if pref == "Morning" else TIME_SLOTS[2:]
        other_slots = [s for s in TIME_SLOTS if s not in pref_slots]

        records = history.get(key, [])

        for _ in range(num_records):
            day  = random.choice(avail)
            # 70% chance of preferred slot
            slot = (random.choice(pref_slots)
                    if random.random() < 0.7
                    else random.choice(other_slots))
            accepted = 1 if slot in pref_slots else (1 if random.random() < 0.3 else 0)
            booked   = random.randint(0, 2)
            size     = random.randint(20, 40)
            ctype    = random.choice(["Standard", "Lab", "Lecture Hall"])

            records.append({
                "day":          day,
                "time_slot":    slot,
                "course_type":  ctype,
                "group_size":   size,
                "booked_today": booked,
                "accepted":     accepted,
            })

        history[key] = records

    save_history(history)
    print(f"[PreferenceModel] Seeded history for {len(teachers)} teacher(s).")


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from database import init_db, get_all_teachers
    from utils import load_sample_data

    init_db()
    load_sample_data()
    teachers = get_all_teachers()

    seed_synthetic_history(teachers)

    pm = PreferenceModel()
    pm.train()

    # Show top-3 ranked slots for teacher 1
    from agents import TeacherAgent
    class FakeModel: pass
    t_data  = teachers[0]
    t_agent = TeacherAgent(1, FakeModel(), t_data)

    course = {"required_room_type": "Standard"}
    ranked = pm.rank_slots(t_agent, course, 30, {})
    print(f"\nTop-3 slots for {t_data['name']}:")
    for day, slot, score in ranked[:3]:
        print(f"  {day} {slot}  score={score:.4f}")