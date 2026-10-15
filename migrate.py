#!/usr/bin/env python3
"""
migrate.py — Prepare the hosted PostgreSQL database used in production.

Local development keeps using SQLite (database/ev_booking.db) completely
unchanged. This script ONLY touches the database named by DATABASE_URL and
NEVER modifies your local SQLite file (it is opened read-only when copying).

Usage:
    python migrate.py --dry-run                # validate the URL and show the plan
    python migrate.py                          # create/verify schema (idempotent)
    python migrate.py --copy-from-sqlite       # ...then copy local data (read-only)

The schema uses CREATE TABLE IF NOT EXISTS and ON CONFLICT DO NOTHING, so
re-running is always safe and never overwrites existing hosted rows.
"""
import argparse
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import (DATABASE_PATH, get_db, init_db, is_postgres,
                         normalize_database_url)

# Copy order respects foreign keys.
TABLES_IN_ORDER = ['users', 'stations', 'charging_points', 'slots',
                   'bookings', 'payments', 'charging_sessions', 'notifications']

# SQLite stores booleans as 0/1 integers; these columns are BOOLEAN in
# PostgreSQL and need an explicit conversion while copying.
BOOLEAN_COLUMNS = {('users', 'is_admin'), ('notifications', 'is_read')}


def mask_url(url):
    """Hide the password before printing a connection string."""
    return re.sub(r'://([^:]+):[^@]+@', r'://\1:****@', url)


def copy_from_sqlite():
    """Copy every table from the local SQLite file into PostgreSQL.

    Existing hosted rows are skipped (ON CONFLICT DO NOTHING); the local
    file is opened in read-only mode and is never written to.
    """
    if not os.path.exists(DATABASE_PATH):
        print(f'[WARN] No local SQLite database at {DATABASE_PATH}; nothing to copy.')
        return

    src = sqlite3.connect(f'file:{DATABASE_PATH.replace(os.sep, "/")}?mode=ro', uri=True)
    src.row_factory = sqlite3.Row
    dst = get_db()
    try:
        for table in TABLES_IN_ORDER:
            try:
                cols = [r[1] for r in src.execute(f'PRAGMA table_info({table})')]
                rows = src.execute(f'SELECT * FROM {table}').fetchall()
            except sqlite3.Error as exc:
                print(f'[SKIP] {table}: {exc}')
                continue
            if not rows:
                print(f'[OK] {table}: 0 rows (nothing to copy)')
                continue

            col_sql = ', '.join(f'"{c}"' for c in cols)
            placeholders = ', '.join(['?'] * len(cols))
            sql = (f'INSERT INTO {table} ({col_sql}) VALUES ({placeholders}) '
                   'ON CONFLICT DO NOTHING')

            inserted = 0
            for row in rows:
                values = []
                for col in cols:
                    value = row[col]
                    if (table, col) in BOOLEAN_COLUMNS and value is not None:
                        value = bool(value)
                    values.append(value)
                inserted += dst.execute(sql, values).rowcount
            dst.commit()
            skipped = len(rows) - inserted
            print(f'[OK] {table}: {len(rows)} rows read, {inserted} inserted, '
                  f'{skipped} skipped (already existed)')
    finally:
        dst.close()
        src.close()


def main():
    parser = argparse.ArgumentParser(
        description='Create/verify the hosted PostgreSQL schema and optionally '
                    'copy data from the local SQLite database.')
    parser.add_argument('--dry-run', action='store_true',
                        help='show what would happen without changing anything')
    parser.add_argument('--copy-from-sqlite', action='store_true',
                        help='copy rows from database/ev_booking.db (read-only) '
                             'into the hosted database')
    args = parser.parse_args()

    if not is_postgres():
        print('[ERROR] DATABASE_URL is not set or is not a postgres:// URL.')
        print('        Set it first, for example:')
        print('        PowerShell:  $env:DATABASE_URL="postgresql://..."')
        print('        bash:        export DATABASE_URL="postgresql://..."')
        sys.exit(1)

    print(f'Target database: {mask_url(normalize_database_url())}')

    if args.dry_run:
        print('[DRY-RUN] Would execute database/schema_postgres.sql '
              '(idempotent: CREATE TABLE IF NOT EXISTS + ON CONFLICT DO NOTHING).')
        print('[DRY-RUN] Would run idempotent column migrations and hash any '
              'legacy plain-text passwords.')
        if args.copy_from_sqlite:
            print(f'[DRY-RUN] Would copy rows from {DATABASE_PATH} (opened read-only) '
                  f'for tables: {", ".join(TABLES_IN_ORDER)}')
        print('[DRY-RUN] No changes were made. Your local SQLite file is never modified.')
        return

    print('Applying schema (safe to re-run)...')
    init_db()
    print('[OK] Schema created/verified.')

    if args.copy_from_sqlite:
        copy_from_sqlite()
        # Re-hash anything the copy brought over as legacy plain text.
        from database.db import _hash_legacy_passwords
        conn = get_db()
        _hash_legacy_passwords(conn)
        conn.commit()
        conn.close()
        print('[OK] Legacy password hashing pass complete.')

    print('Done. The hosted database is ready for the Vercel deployment.')


if __name__ == '__main__':
    main()

