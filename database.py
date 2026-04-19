import sqlite3

# This is the name of the file where all your data will be saved.
DB_PATH = "timetable.db"

def get_connection():
    """
    Connects Python to the database file.
    'row_factory' allows us to access data by name (like row['name']) 
    instead of just by position (like row[0]).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    The 'master' setup function. It calls create_tables() and 
    prints a message to let you know everything is ready.
    """
    create_tables()
    print(f"[DB] Database initialized at '{DB_PATH}'")

def create_tables():
    """
    Creates the structure for the database. Think of this as creating 
    the tabs in an Excel file: Teachers, Groups, Classrooms, etc.
    """
    conn = get_connection()
    cursor = conn.cursor() # The 'cursor' is like a pointer used to execute commands.

    # executescript runs multiple SQL commands at once to build the tables.
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS Teachers (
            teacher_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            available_days TEXT   NOT NULL,
            preferred_time TEXT   NOT NULL
        );

        CREATE TABLE IF NOT EXISTS StudentGroups (
            group_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            program     TEXT    NOT NULL,
            year        INTEGER NOT NULL,
            group_size  INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Classrooms (
            room_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            capacity    INTEGER NOT NULL,
            equipment   TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Courses (
            course_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name        TEXT    NOT NULL,
            teacher_id         INTEGER NOT NULL,
            group_id           INTEGER NOT NULL,
            required_room_type TEXT    NOT NULL,
            FOREIGN KEY (teacher_id) REFERENCES Teachers(teacher_id),
            FOREIGN KEY (group_id)   REFERENCES StudentGroups(group_id)
        );

        CREATE TABLE IF NOT EXISTS Schedule (
            session_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id   INTEGER NOT NULL,
            room_id     INTEGER NOT NULL,
            day         TEXT    NOT NULL,
            time_slot   TEXT    NOT NULL,
            FOREIGN KEY (course_id) REFERENCES Courses(course_id),
            FOREIGN KEY (room_id)   REFERENCES Classrooms(room_id)
        );
    """)

    conn.commit() # This 'saves' the changes.
    conn.close()  # Always close the connection when finished.
    print("[DB] All tables created successfully.")


def insert_teacher(name, available_days, preferred_time):
    """
    Adds a new teacher to the Teachers table.
    It returns the 'teacher_id' (a unique number) assigned to them.
    """
    conn = get_connection()
    cursor = conn.cursor()
    # Using '?' prevents SQL Injection (a security risk).
    cursor.execute(
        "INSERT INTO Teachers (name, available_days, preferred_time) VALUES (?, ?, ?)",
        (name, available_days, preferred_time)
    )
    conn.commit()
    teacher_id = cursor.lastrowid # Gets the ID number created by the database.
    conn.close()
    print(f"[DB] Teacher inserted: id={teacher_id}, name={name}")
    return teacher_id

def insert_group(program, year, group_size):
    """
    Adds a group of students (e.g., 'Computer Science, Year 1').
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO StudentGroups (program, year, group_size) VALUES (?, ?, ?)",
        (program, year, group_size)
    )
    conn.commit()
    group_id = cursor.lastrowid
    conn.close()
    print(f"[DB] Group inserted: id={group_id}, program={program}, year={year}")
    return group_id

def insert_classroom(capacity, equipment):
    """
    Adds a physical room to the database with its size and tools (like Projectors).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Classrooms (capacity, equipment) VALUES (?, ?)",
        (capacity, equipment)
    )
    conn.commit()
    room_id = cursor.lastrowid
    conn.close()
    print(f"[DB] Classroom inserted: id={room_id}, capacity={capacity}")
    return room_id

def insert_course(course_name, teacher_id, group_id, required_room_type):
    """
    Connects a subject name to a specific teacher and a student group.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO Courses (course_name, teacher_id, group_id, required_room_type)
           VALUES (?, ?, ?, ?)""",
        (course_name, teacher_id, group_id, required_room_type)
    )
    conn.commit()
    course_id = cursor.lastrowid
    conn.close()
    print(f"[DB] Course inserted: id={course_id}, name={course_name}")
    return course_id

def insert_session(course_id, room_id, day, time_slot):
    """
    This is the final step: putting a course into a specific room at a specific time.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Schedule (course_id, room_id, day, time_slot) VALUES (?, ?, ?, ?)",
        (course_id, room_id, day, time_slot)
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    print(f"[DB] Session inserted: id={session_id}, course={course_id}, day={day}, slot={time_slot}")
    return session_id

def get_all_teachers():
    """Retrieves every teacher record and turns them into a Python list of dictionaries."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Teachers")
    # This list comprehension converts raw database rows into readable dicts.
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

# The next three functions (get_all_groups, classrooms, courses) 
# work exactly like get_all_teachers, just pulling from different tables.

def get_all_groups():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM StudentGroups")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_all_classrooms():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Classrooms")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_all_courses():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Courses")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_schedule():
    """
    This is the most complex function. It uses 'JOIN' to combine 
    data from all tables into one big, human-readable timetable.
    Instead of just showing 'course_id: 1', it shows 'Course Name: Math'.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            s.session_id,
            s.day,
            s.time_slot,
            c.course_name,
            t.name        AS teacher_name,
            g.program     AS group_program,
            g.year        AS group_year,
            r.room_id,
            r.capacity    AS room_capacity,
            r.equipment
        FROM Schedule s
        JOIN Courses       c ON s.course_id  = c.course_id
        JOIN Teachers      t ON c.teacher_id = t.teacher_id
        JOIN StudentGroups g ON c.group_id   = g.group_id
        JOIN Classrooms    r ON s.room_id    = r.room_id
        ORDER BY s.day, s.time_slot
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def clear_schedule():
    """
    Wipes the Schedule table clean. 
    Useful if you want to generate a brand new timetable from scratch.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Schedule")
    conn.commit()
    deleted = cursor.rowcount # Tells you how many rows were deleted.
    conn.close()
    print(f"[DB] Schedule cleared: {deleted} session(s) removed.")

    