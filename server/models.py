import sqlite3

DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device TEXT,
        url TEXT,
        category TEXT,
        time TEXT
    )
    """)

    conn.commit()
    conn.close()


def log_violation(device, url, category, time):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        INSERT INTO violations (device, url, category, time)
        VALUES (?, ?, ?, ?)
    """, (device, url, category, time))

    conn.commit()
    conn.close()


def get_category_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT category, COUNT(*)
        FROM violations
        GROUP BY category
    """)

    data = c.fetchall()
    conn.close()
    return data


def get_total_count():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM violations")
    total = c.fetchone()[0]

    conn.close()
    return total