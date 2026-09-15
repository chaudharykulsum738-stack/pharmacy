from functools import wraps
from flask import session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection


def register_user(name, email, password):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return False, "An account with this email already exists."

    password_hash = generate_password_hash(password)
    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash)
    )
    new_user_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO cabinets (user_id, cabinet_name, priority_level, capacity) VALUES
        (?, 'Cabinet A - Front Counter', 'High', 50),
        (?, 'Cabinet B - Mid Shelf', 'Medium', 100),
        (?, 'Cabinet C - Back Storage', 'Low', 200)
    """, (new_user_id, new_user_id, new_user_id))

    conn.commit()
    cursor.close()
    conn.close()
    return True, "Account created successfully."


def authenticate_user(email, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return False, "Invalid email or password."

    return True, user


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


def current_user_id():
    return session.get("user_id")
