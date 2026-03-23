import sqlite3
import json
from datetime import datetime

DB_PATH = "student_records.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            created_at TEXT,
            raw_text TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS extracted_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            item_type TEXT,  -- 'theory' or 'book'
            item_name TEXT,
            context TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            major TEXT,
            score INTEGER,
            reason TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)
    conn.commit()
    conn.close()


def save_student(name: str, raw_text: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO students (name, created_at, raw_text) VALUES (?, ?, ?)",
        (name, datetime.now().isoformat(), raw_text)
    )
    student_id = c.lastrowid
    conn.commit()
    conn.close()
    return student_id


def save_extracted_items(student_id: int, theories: list, books: list):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for theory in theories:
        c.execute(
            "INSERT INTO extracted_items (student_id, item_type, item_name, context) VALUES (?, ?, ?, ?)",
            (student_id, "theory", theory.get("name", ""), theory.get("context", ""))
        )
    for book in books:
        c.execute(
            "INSERT INTO extracted_items (student_id, item_type, item_name, context) VALUES (?, ?, ?, ?)",
            (student_id, "book", book.get("name", ""), book.get("context", ""))
        )
    conn.commit()
    conn.close()


def save_recommendations(student_id: int, recommendations: list):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for rec in recommendations:
        c.execute(
            "INSERT INTO recommendations (student_id, major, score, reason) VALUES (?, ?, ?, ?)",
            (student_id, rec.get("major", ""), rec.get("score", 0), rec.get("reason", ""))
        )
    conn.commit()
    conn.close()


def get_all_students():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, created_at FROM students ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows


def get_student_data(student_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = c.fetchone()
    c.execute("SELECT item_type, item_name, context FROM extracted_items WHERE student_id = ?", (student_id,))
    items = c.fetchall()
    c.execute("SELECT major, score, reason FROM recommendations WHERE student_id = ? ORDER BY score DESC", (student_id,))
    recs = c.fetchall()
    conn.close()
    return student, items, recs
