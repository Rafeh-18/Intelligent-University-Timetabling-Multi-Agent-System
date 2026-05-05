# 🎓 Intelligent University Timetabling — Multi-Agent System

> A distributed Multi-Agent System (MAS) for automatic university timetable generation using negotiation, constraint satisfaction, and cooperative scheduling.

---

## 📌 Project Overview

This project is part of the **Intelligent University Observatory** initiative. It implements a Multi-Agent System (MAS) using the **Mesa** Python framework to solve the university timetabling problem — one of the most complex combinatorial optimization problems in academic institutions.

Agents representing **teachers**, **student groups**, and **classrooms** negotiate autonomously to allocate time slots while respecting institutional constraints such as availability, capacity, and equipment requirements.

---

## 🏗️ Project Structure

```
timetabling_mas/
│
├── agents.py          # All MAS agents (Teacher, Group, Room, Scheduler, Constraint, Interface)
├── model.py           # Mesa TimetablingModel — orchestrates the simulation
├── scheduler.py       # Core scheduling logic (slot allocation, conflict resolution)
├── database.py        # SQLite database layer (CRUD operations)
├── app.py             # Flask web interface and API routes
├── utils.py           # Utility functions (data loading, CSV export, formatting)
└── README.md
```

---

## 🤖 Agent Architecture

| Agent | Role |
|---|---|
| `SchedulerAgent` | Coordinates the scheduling process and manages timetable generation |
| `TeacherAgent` | Represents a teacher with availability and time preferences |
| `GroupAgent` | Represents a student group, prevents conflicting session assignments |
| `RoomAgent` | Manages classroom availability, capacity, and equipment |
| `ConstraintAgent` | Verifies institutional constraints and detects conflicts |
| `InterfaceAgent` | Exposes the timetable through the web dashboard |

---

## 🗄️ Database Schema

```
Teachers       (teacher_id, name, available_days, preferred_time)
StudentGroups  (group_id, program, year, group_size)
Classrooms     (room_id, capacity, equipment)
Courses        (course_id, course_name, teacher_id, group_id, required_room_type)
Schedule       (session_id, course_id, room_id, day, time_slot)
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| MAS Framework | [Mesa](https://mesa.readthedocs.io/) |
| Backend | Python 3.10+ |
| Web Interface | Flask |
| Database | SQLite |
| Data Processing | Pandas, NumPy |
| Visualization | Plotly, Matplotlib |
| ML (optional) | Scikit-learn |

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/Rafeh-18/Intelligent-University-Timetabling-Multi-Agent-System.git
cd Intelligent-University-Timetabling-Multi-Agent-System-main
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize the database
```bash
python database.py
```

### 4. Load sample data
```bash
python utils.py
```

### 5. Run the MAS simulation
```bash
python model.py
```

### 6. Launch the web interface
```bash
python app.py
```
Then open `http://localhost:5000` in your browser.

---

## 🌐 Web Interface Routes

| Route | Method | Description |
|---|---|---|
| `/` | GET | Dashboard homepage |
| `/run` | POST | Trigger timetable generation |
| `/timetable` | GET | Return full schedule as JSON |
| `/stats` | GET | Return scheduling statistics |
| `/reset` | POST | Clear the current schedule |

---

## 📦 Requirements

```
mesa
flask
pandas
numpy
matplotlib
plotly
scikit-learn
```

> Install all with: `pip install -r requirements.txt`

---

## 📅 Project Planning

| Week | Phase | Description |
|---|---|---|
| 1 | Setup & Design | Requirements, DB schema, agent architecture |
| 2 | Core Development | TeacherAgent, GroupAgent, RoomAgent |
| 3 | Coordination & Negotiation | Conflict detection, negotiation protocols |
| 4 | Integration & Finalization | Web interface, testing, report, demo |

---

## 📊 Evaluation Criteria

- ✅ Quality of Multi-Agent System design
- ✅ Communication and negotiation between agents
- ✅ Effectiveness of scheduling strategies
- ✅ Database integration
- ✅ Usability of the web dashboard
- ✅ Documentation and presentation quality

---

## 🔧 Optional Extensions

- 🔲 Auction-based scheduling mechanisms
- 🔲 Game-theoretic negotiation strategies
- 🔲 ML models for predicting teacher preferences
- 🔲 Interactive timetable editing interface
- 🔲 Large-scale simulation experiments

---

## 👥 Team

| Name | Role |
|---|---|
| Rafeh Maddouri | MAS & Agent Design |
| Rafeh Maddouri | Database & Backend |
| Rafeh Maddouri | Web Interface & Dashboard |
| Rafeh Maddouri | Report & Documentation |

---

## 📄 License

This project is developed as part of a university course on **Distributed and Collaborative AI 2025-2026**. For academic use only.
