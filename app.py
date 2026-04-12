"""
app.py - Flask Web Interface for University Timetabling MAS
"""

from flask import Flask, render_template, jsonify
from database import get_schedule, clear_schedule, init_db
from scheduler import generate_timetable, validate_schedule
from utils import load_sample_data

app = Flask(__name__)


@app.route("/")
def index():
    """Serve the dashboard."""
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run_scheduler():
    """
    Trigger the MAS scheduling simulation (Nash + ML by default).
    Returns timetable, summary, and negotiation log.
    """
    try:
        results   = generate_timetable()
        return jsonify({
            "timetable":   results.get("timetable", []),
            "summary":     results.get("summary", {}),
            "negotiation": results.get("negotiation", {}),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/timetable")
def get_timetable_json():
    """Return the current schedule from DB plus a quick summary."""
    try:
        sessions = get_schedule()
        summary  = {
            "total_courses":   None,
            "scheduled":       len(sessions),
            "unresolved":      None,
            "unresolved_list": [],
        }
        return jsonify({"sessions": sessions, "summary": summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/stats")
def get_stats():
    """Return a full validation report on the current schedule."""
    try:
        sessions = get_schedule()
        report   = validate_schedule(sessions)
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/reset", methods=["POST"])
def reset_schedule():
    """Clear the schedule table."""
    try:
        clear_schedule()
        return jsonify({"status": "ok", "message": "Schedule cleared."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    init_db()
    load_sample_data()
    app.run(debug=True, port=5000)