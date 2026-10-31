import sqlite3
import hashlib
from db import cursor, conn


def _hash(password: str) -> str:
    """SHA-256 hash of the password."""
    return hashlib.sha256(password.encode()).hexdigest()


def register(username: str, password: str) -> bool:
    """
    Register a new user.
    Returns True on success, False if the username is already taken.
    """
    try:
        cursor.execute(
            "INSERT INTO users VALUES (?, ?)",
            (username, _hash(password)),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # username is PRIMARY KEY -> duplicate raises IntegrityError
        return False


def login(username: str, password: str):
    """
    Return the user row if credentials are valid, else None.
    """
    cursor.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, _hash(password)),
    )
    return cursor.fetchone()
