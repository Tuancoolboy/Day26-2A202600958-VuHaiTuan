from __future__ import annotations

import sqlite3
from pathlib import Path

from db import DEFAULT_DB_PATH


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    age INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    semester TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE(student_id, course_id, semester)
);
"""

STUDENTS = [
    ("An Nguyen", "A1", "an.nguyen@example.edu", 20),
    ("Binh Tran", "A1", "binh.tran@example.edu", 21),
    ("Chi Le", "A2", "chi.le@example.edu", 20),
    ("Dung Pham", "A2", "dung.pham@example.edu", 22),
    ("Ha Vu", "B1", "ha.vu@example.edu", 23),
    ("Minh Do", "B1", "minh.do@example.edu", 21),
]

COURSES = [
    ("MCP101", "Model Context Protocol Fundamentals", 3),
    ("DB201", "Practical Databases", 4),
    ("AI301", "Applied AI Engineering", 3),
]

ENROLLMENTS = [
    (1, 1, 91.5, "2026-Spring"),
    (1, 2, 87.0, "2026-Spring"),
    (2, 1, 78.0, "2026-Spring"),
    (2, 3, 84.5, "2026-Spring"),
    (3, 1, 95.0, "2026-Spring"),
    (3, 2, 90.0, "2026-Spring"),
    (4, 2, 72.0, "2026-Spring"),
    (4, 3, 80.0, "2026-Spring"),
    (5, 1, 88.0, "2026-Spring"),
    (5, 3, 92.0, "2026-Spring"),
    (6, 2, 69.5, "2026-Spring"),
    (6, 3, 76.0, "2026-Spring"),
]


def create_database(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.executemany(
            "INSERT INTO students (name, cohort, email, age) VALUES (?, ?, ?, ?)",
            STUDENTS,
        )
        connection.executemany(
            "INSERT INTO courses (code, title, credits) VALUES (?, ?, ?)",
            COURSES,
        )
        connection.executemany(
            "INSERT INTO enrollments (student_id, course_id, score, semester) VALUES (?, ?, ?, ?)",
            ENROLLMENTS,
        )
        connection.commit()
    return db_path


if __name__ == "__main__":
    path = create_database()
    print(f"SQLite database initialized at {path}")
