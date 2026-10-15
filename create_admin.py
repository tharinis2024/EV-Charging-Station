#!/usr/bin/env python3
"""
create_admin.py — Development utility to create or promote an admin account.

Usage:
    python create_admin.py                          # interactive prompt
    python create_admin.py --email admin@example.com --password secret --name "Admin User"
    python create_admin.py --promote admin@example.com  # promote existing user to admin

This script is for DEVELOPMENT and DEMO USE ONLY.
Do not run it in a production environment with real user data.
"""

import argparse
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import get_db, init_db
from werkzeug.security import generate_password_hash


def promote_existing(email: str) -> None:
    """Promote an existing user account to admin by email."""
    conn = get_db()
    user = conn.execute('SELECT id, name, email, is_admin FROM users WHERE email = ?', (email,)).fetchone()
    if not user:
        print(f"[ERROR] No user found with email: {email}")
        conn.close()
        sys.exit(1)
    if user['is_admin']:
        print(f"[INFO] {user['name']} ({email}) is already an admin.")
        conn.close()
        return
    conn.execute('UPDATE users SET is_admin = TRUE WHERE email = ?', (email,))
    conn.commit()
    conn.close()
    print(f"[OK] {user['name']} ({email}) has been promoted to admin.")


def create_or_update(email: str, password: str, name: str) -> None:
    """Create a new admin account or update/promote an existing one."""
    if len(password) < 6:
        print("[ERROR] Password must be at least 6 characters.")
        sys.exit(1)

    hashed = generate_password_hash(password)
    conn = get_db()
    existing = conn.execute('SELECT id, name, is_admin FROM users WHERE email = ?', (email,)).fetchone()

    if existing:
        # Update password and promote to admin
        conn.execute('UPDATE users SET password = ?, is_admin = 1, name = ? WHERE email = ?',
                     (hashed, name, email))
        action = 'updated and promoted'
    else:
        # Insert brand-new admin user
        conn.execute(
            'INSERT INTO users (name, email, phone, password, is_admin) VALUES (?, ?, ?, ?, TRUE)',
            (name, email, '0000000000', hashed)
        )
        action = 'created'

    conn.commit()
    conn.close()
    print(f"[OK] Admin account {action}: {name} <{email}>")
    print(f"     Login at http://localhost:5000/login with email='{email}' and your chosen password.")


def interactive() -> None:
    """Prompt the user for account details interactively."""
    print("=== EV ChargePoint — Create/Promote Admin Account ===\n")
    name = input("Full name [Admin User]: ").strip() or "Admin User"
    email = input("Email [admin@example.com]: ").strip() or "admin@example.com"
    import getpass
    password = getpass.getpass("Password (min 6 chars): ")
    if len(password) < 6:
        print("[ERROR] Password too short.")
        sys.exit(1)
    create_or_update(email, password, name)


def main():
    parser = argparse.ArgumentParser(description="Create or promote admin account")
    parser.add_argument('--email', help='Admin email address')
    parser.add_argument('--password', help='Admin password (min 6 chars)')
    parser.add_argument('--name', default='Admin User', help='Display name')
    parser.add_argument('--promote', metavar='EMAIL',
                        help='Promote an existing account to admin without changing password')
    args = parser.parse_args()

    # Make sure the DB and schema are initialised
    init_db()

    if args.promote:
        promote_existing(args.promote)
    elif args.email and args.password:
        create_or_update(args.email, args.password, args.name)
    else:
        interactive()


if __name__ == '__main__':
    main()
