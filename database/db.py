import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'ev_booking.db')

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r') as f:
        conn.executescript(f.read())
    _apply_migrations(conn)
    conn.commit()
    conn.close()


def _apply_migrations(conn):
    """Idempotent migrations for databases created before newer columns existed."""
    point_cols = [row[1] for row in conn.execute('PRAGMA table_info(charging_points)')]
    if 'status' not in point_cols:
        conn.execute("ALTER TABLE charging_points ADD COLUMN status TEXT DEFAULT 'ACTIVE'")
