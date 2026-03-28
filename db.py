import sqlite3

# Connect DB
conn = sqlite3.connect("leads.db", check_same_thread=False)
cursor = conn.cursor()

# ---------------- CREATE TABLE ----------------
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

# ---------------- ADD NEW COLUMN SAFELY ----------------
try:
    cursor.execute("ALTER TABLE users ADD COLUMN slots_json TEXT")
    conn.commit()
    print("✅ slots_json column added")
except:
    # Column already exists
    print("ℹ️ slots_json already exists")

# ---------------- DB FUNCTIONS ----------------
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