"""
app.py - Flask Web Interface for University Timetabling MAS
"""

from flask import Flask, render_template, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    pass


@app.route("/run", methods=["POST"])
def run_scheduler():
    pass


@app.route("/timetable")
def get_timetable_json():
    pass


@app.route("/stats")
def get_stats():
    pass


@app.route("/reset", methods=["POST"])
def reset_schedule():
    pass


if __name__ == "__main__":
    app.run(debug=True)
