import sqlite3

conn = sqlite3.connect("leads.db", check_same_thread=False)
cursor = conn.cursor()

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_number TEXT PRIMARY KEY,
    state TEXT,
    name TEXT,
    phone TEXT,
    place TEXT
)
""")
conn.commit()


def get_user(user):
    cursor.execute("SELECT * FROM users WHERE user_number=?", (user,))
    return cursor.fetchone()


def create_user(user):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_number, state) VALUES (?, ?)",
        (user, "start")
    )
    conn.commit()


def update_user(user, field, value):
    cursor.execute(
        f"UPDATE users SET {field}=? WHERE user_number=?",
        (value, user)
    )
    conn.commit()