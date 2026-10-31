import sqlite3

conn = sqlite3.connect("hand_cricket.db", check_same_thread=False)
cursor = conn.cursor()

def create_tables():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            score    INTEGER NOT NULL,
            result   TEXT NOT NULL
        )
    """)
    conn.commit()
