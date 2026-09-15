import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "pharmacy.db")


class DictCursor(sqlite3.Cursor):
    def fetchone(self):
        row = super().fetchone()
        if row is None:
            return None
        return {col[0]: row[idx] for idx, col in enumerate(self.description)}

    def fetchall(self):
        rows = super().fetchall()
        return [{col[0]: row[idx] for idx, col in enumerate(self.description)} for row in rows]


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = dict_factory
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as e:
        print(f"Database connection failed: {e}")
        return None
