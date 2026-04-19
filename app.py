"""
app.py - Flask Web Interface for University Timetabling MAS

Routes
------
GET  /              Dashboard HTML
POST /run           Trigger timetable generation
GET  /timetable     Return current schedule as JSON
GET  /stats         Return validation report
POST /reset         Clear the schedule
"""

from __future__ import annotations

import os
from functools import wraps
from typing import Any

from flask import Flask, render_template, jsonify, request, abort

from config import FLASK_PORT, FLASK_DEBUG, API_TOKEN
from database import get_schedule, clear_schedule, init_db
from scheduler import generate_timetable, validate_schedule
from utils import load_sample_data

app = Flask(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Optional token-based auth  (set API_TOKEN env var to enable)
# ─────────────────────────────────────────────────────────────────────────────

def require_token(f):
    """
    Decorator: checks X-API-Token header when API_TOKEN is configured.
    In development (API_TOKEN=""), all requests pass through.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if API_TOKEN and request.headers.get("X-API-Token") != API_TOKEN:
            abort(403, description="Invalid or missing API token.")
        return f(*args, **kwargs)
    return decorated


def success(data: dict, status: int = 200):
    return jsonify({"ok": True,  **data}), status


def error(message: str, status: int = 500):
    return jsonify({"ok": False, "error": message}), status


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the dashboard."""
    return render_template("index.html")


@app.route("/run", methods=["POST"])
@require_token
def run_scheduler():
    """
    Trigger MAS scheduling. Clears the existing schedule and generates a new one.

    Response JSON
    -------------
    {
        "ok": true,
        "timetable":   [...],
        "summary":     {...},
        "negotiation": {...}
    }
    """
    try:
        results = generate_timetable()
        return success({
            "timetable":   results.get("timetable", []),
            "summary":     results.get("summary", {}),
            "negotiation": results.get("negotiation", {}),
        })
    except ValueError as exc:
        # DB not seeded, etc.
        return error(str(exc), status=400)
    except Exception as exc:
        app.logger.exception("Scheduler error")
        return error(str(exc), status=500)


@app.route("/timetable")
def get_timetable_json():
    """
    Return the current schedule from the DB plus a lightweight summary.
    Does NOT re-run the scheduler.
    """
    try:
        sessions = get_schedule()
        summary  = {
            "total_courses":   None,
            "scheduled":       len(sessions),
            "unresolved":      None,
            "unresolved_list": [],
        }
        return success({"sessions": sessions, "summary": summary})
    except Exception as exc:
        app.logger.exception("Timetable fetch error")
        return error(str(exc))


@app.route("/stats")
def get_stats():
    """Return a full validation report for the current schedule."""
    try:
        from database import get_all_courses
        sessions      = get_schedule()
        total_courses = len(get_all_courses())
        report        = validate_schedule(sessions, total_courses=total_courses)
        return success(report)
    except Exception as exc:
        app.logger.exception("Stats error")
        return error(str(exc))


@app.route("/reset", methods=["POST"])
@require_token
def reset_schedule():
    """Clear the schedule table. Requires the API token if one is configured."""
    try:
        deleted = clear_schedule()
        return success({"message": f"Schedule cleared — {deleted} session(s) removed."})
    except Exception as exc:
        app.logger.exception("Reset error")
        return error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Error handlers
# ─────────────────────────────────────────────────────────────────────────────

@app.errorhandler(403)
def forbidden(exc):
    return jsonify({"ok": False, "error": str(exc)}), 403


@app.errorhandler(404)
def not_found(exc):
    return jsonify({"ok": False, "error": "Not found"}), 404


@app.errorhandler(405)
def method_not_allowed(exc):
    return jsonify({"ok": False, "error": "Method not allowed"}), 405


# ─────────────────────────────────────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    load_sample_data()
    app.run(debug=FLASK_DEBUG, port=FLASK_PORT)