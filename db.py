import sqlite3
import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "studio.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            filename TEXT NOT NULL,
            prompt TEXT,
            preset TEXT,
            is_vector INTEGER DEFAULT 0,
            title TEXT,
            keywords TEXT,
            keywords_ko TEXT,
            stock_category_id INTEGER,
            status TEXT DEFAULT 'generated',
            created_at TEXT
        )
        """
    )
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(images)")}
    if "keywords_ko" not in existing:
        conn.execute("ALTER TABLE images ADD COLUMN keywords_ko TEXT")
    conn.commit()
    conn.close()


def insert_image(filename, prompt, preset, is_vector=0):
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    cur = conn.execute(
        "INSERT INTO images (filename, prompt, preset, is_vector, created_at) VALUES (?,?,?,?,?)",
        (filename, prompt, preset, is_vector, now),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_image(image_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_images():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM images ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_image(image_id, **fields):
    if not fields:
        return
    conn = get_conn()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [image_id]
    conn.execute(f"UPDATE images SET {set_clause} WHERE id=?", values)
    conn.commit()
    conn.close()
