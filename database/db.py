import os
import sqlite3

# ---------------------------------------------------------------------------
# Database selection
#   * Local development: SQLite file (unchanged behaviour).
#   * Production (Vercel): hosted PostgreSQL via the DATABASE_URL env var.
# ---------------------------------------------------------------------------
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'ev_booking.db')
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

_SCHEMA_DIR = os.path.dirname(__file__)
SQLITE_SCHEMA = os.path.join(_SCHEMA_DIR, 'schema.sql')
POSTGRES_SCHEMA = os.path.join(_SCHEMA_DIR, 'schema_postgres.sql')


def is_postgres():
    """True when a hosted PostgreSQL URL is configured (production)."""
    return bool(DATABASE_URL) and DATABASE_URL.startswith(('postgres://', 'postgresql://'))


def normalize_database_url(url=None):
    """Make a hosted-DB URL libpq-safe: postgres:// -> postgresql:// and
    default to TLS unless the caller explicitly configured sslmode."""
    url = url or DATABASE_URL
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    if 'sslmode=' not in url:
        url += ('&' if '?' in url else '?') + 'sslmode=require'
    return url


def translate_query(query):
    """Translate SQLite-style '?' placeholders to psycopg '%s'.

    Every literal '%' is doubled so psycopg2's own %-interpolation leaves it
    intact (important for LIKE '%...%' patterns). Content inside
    single-quoted strings and double-quoted identifiers is preserved,
    apart from the '%' escaping psycopg2 requires everywhere.
    """
    out = []
    i = 0
    n = len(query)
    in_single = False
    in_double = False
    while i < n:
        ch = query[i]
        if in_single:
            if ch == '%':
                out.append('%%')
            else:
                out.append(ch)
            if ch == "'":
                if i + 1 < n and query[i + 1] == "'":   # '' escaped quote
                    out.append("'")
                    i += 2
                    continue
                in_single = False
            i += 1
            continue
        if in_double:
            if ch == '%':
                out.append('%%')
            else:
                out.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            out.append(ch)
        elif ch == '"':
            in_double = True
            out.append(ch)
        elif ch == '?':
            out.append('%s')
        elif ch == '%':
            out.append('%%')
        else:
            out.append(ch)
        i += 1
    return ''.join(out)



class PgRow:
    """sqlite3.Row-compatible row for PostgreSQL results.

    Supports row['name'], row[0], iteration over values and dict(row),
    which is exactly how the routes consume rows.
    """

    __slots__ = ('_keys', '_values')

    def __init__(self, description, values):
        self._keys = [col[0] for col in description]
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._keys.index(key)]

    def keys(self):
        return list(self._keys)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return 'PgRow(%r)' % dict(zip(self._keys, self._values))


class PgCursor:
    """Cursor wrapper returning PgRow objects (sqlite3.Cursor-like)."""

    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def execute(self, query, params=()):
        self._cursor.execute(translate_query(query), params if params else None)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return PgRow(self._cursor.description, row)

    def fetchall(self):
        description = self._cursor.description
        return [PgRow(description, row) for row in self._cursor.fetchall()]

    def __iter__(self):
        description = self._cursor.description
        for row in self._cursor:
            yield PgRow(description, row)

    def close(self):
        self._cursor.close()


class PgConnection:
    """sqlite3.Connection-like wrapper around a psycopg2 connection."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, query, params=()):
        return PgCursor(self._connection.cursor()).execute(query, params)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def get_db():
    """Return a database connection for the active backend."""
    if is_postgres():
        try:
            import psycopg2
        except ImportError as exc:
            raise RuntimeError(
                'DATABASE_URL is set but psycopg2 is not installed. '
                'Install it with: pip install psycopg2-binary'
            ) from exc
        return PgConnection(psycopg2.connect(normalize_database_url()))
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables and run idempotent migrations for the active backend.

    Safe to run repeatedly: the schema uses IF NOT EXISTS / ON CONFLICT
    DO NOTHING and the migrations below are no-ops once applied.
    """
    conn = get_db()
    schema_path = POSTGRES_SCHEMA if is_postgres() else SQLITE_SCHEMA
    with open(schema_path, 'r', encoding='utf-8') as f:
        script = f.read()
    if is_postgres():
        conn.execute(script)          # psycopg2 runs multi-statement scripts
    else:
        conn.executescript(script)    # sqlite3 needs executescript for scripts
    _apply_migrations(conn)
    conn.commit()
    conn.close()


def _apply_migrations(conn):
    """Idempotent migrations for databases created before newer columns existed."""
    if is_postgres():
        row = conn.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'charging_points' AND column_name = 'status'"
        ).fetchone()
        if row and row[0] == 0:
            conn.execute("ALTER TABLE charging_points ADD COLUMN status TEXT DEFAULT 'ACTIVE'")
    else:
        point_cols = [row[1] for row in conn.execute('PRAGMA table_info(charging_points)')]
        if 'status' not in point_cols:
            conn.execute("ALTER TABLE charging_points ADD COLUMN status TEXT DEFAULT 'ACTIVE'")
    _hash_legacy_passwords(conn)



def _hash_legacy_passwords(conn):
    """Hash any plain-text passwords left behind by old seed data.

    Safe to run repeatedly: rows already protected by a werkzeug hash
    (pbkdf2:... / scrypt:...) are left untouched.
    """
    rows = conn.execute(
        "SELECT id, password FROM users WHERE password NOT LIKE 'pbkdf2:%' AND password NOT LIKE 'scrypt:%'"
    ).fetchall()
    if not rows:
        return
    from werkzeug.security import generate_password_hash
    for row in rows:
        conn.execute('UPDATE users SET password = ? WHERE id = ?',
                     (generate_password_hash(row['password']), row['id']))
