"""
Focused tests for the extended Admin Module.

Covers: auth guards (401/403/redirects), dashboard stats, booking filters,
safe booking status transitions, duplicate-slot prevention, point deactivation
guards, protected user deletion, input validation, and password exposure.

Run the app first:  python app.py   then:  python test_admin_extended.py
"""
import os
import sqlite3
import sys
import time

import requests

BASE_URL = 'http://localhost:5000'
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'ev_booking.db')

TEST_DATE = '2027-06-15'
TEST_STATION = 'Extended Test Station'


def check(name, condition, extra=''):
    assert condition, f'{name} FAILED {extra}'
    print(f'PASS - {name}')


def cleanup_database(test_emails, station_name):
    """Remove every row this test created so repeat runs stay deterministic."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        station = conn.execute('SELECT id FROM stations WHERE name = ?', (station_name,)).fetchone()
        if station:
            point_ids = [r['id'] for r in conn.execute(
                'SELECT id FROM charging_points WHERE station_id = ?', (station['id'],))]
            slot_ids = []
            for pid in point_ids:
                slot_ids += [r['id'] for r in conn.execute(
                    'SELECT id FROM slots WHERE point_id = ?', (pid,))]
            for sid in slot_ids:
                booking_ids = [r['id'] for r in conn.execute(
                    'SELECT id FROM bookings WHERE slot_id = ?', (sid,))]
                for bid in booking_ids:
                    conn.execute('DELETE FROM payments WHERE booking_id = ?', (bid,))
                    conn.execute('DELETE FROM charging_sessions WHERE booking_id = ?', (bid,))
                    conn.execute('DELETE FROM notifications WHERE message LIKE ?', (f'%{bid}%',))
                    conn.execute('DELETE FROM bookings WHERE id = ?', (bid,))
                conn.execute('DELETE FROM slots WHERE id = ?', (sid,))
            for pid in point_ids:
                conn.execute('DELETE FROM charging_points WHERE id = ?', (pid,))
            conn.execute('DELETE FROM stations WHERE id = ?', (station['id'],))

        for email in test_emails:
            user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
            if user:
                booking_ids = [r['id'] for r in conn.execute(
                    'SELECT id FROM bookings WHERE user_id = ?', (user['id'],))]
                for bid in booking_ids:
                    conn.execute('DELETE FROM payments WHERE booking_id = ?', (bid,))
                    conn.execute('DELETE FROM charging_sessions WHERE booking_id = ?', (bid,))
                    conn.execute('DELETE FROM notifications WHERE message LIKE ?', (f'%{bid}%',))
                    conn.execute('DELETE FROM bookings WHERE id = ?', (bid,))
                conn.execute('DELETE FROM notifications WHERE user_id = ?', (user['id'],))
                conn.execute('DELETE FROM users WHERE id = ?', (user['id'],))
        conn.commit()
    finally:
        conn.close()


def test_admin_extended():
    print('Testing extended admin module...')
    admin_email = 'admin@example.com'
    user_email = 'ext_normal@example.com'
    doomed_email = 'ext_doomed@example.com'
    test_emails = [user_email, doomed_email]

    try:
        # ---------- 1. Unauthenticated access ----------
        print('1. Unauthenticated access...')
        anon = requests.Session()
        res = anon.get(f'{BASE_URL}/admin', allow_redirects=False)
        check('anon GET /admin redirects to admin login',
              res.status_code in (301, 302) and '/admin/login' in res.headers.get('Location', ''),
              f"{res.status_code} {res.headers.get('Location')}")
        res = anon.get(f'{BASE_URL}/api/admin/stats')
        check('anon GET /api/admin/stats -> 401', res.status_code == 401, res.status_code)
        res = anon.delete(f'{BASE_URL}/api/admin/users/1')
        check('anon DELETE /api/admin/users/1 -> 401', res.status_code == 401, res.status_code)

        # Visible admin login entry points
        res = anon.get(f'{BASE_URL}/admin/login')
        check('anon GET /admin/login -> 200', res.status_code == 200, res.status_code)
        check('admin login page has dedicated form',
              'id="admin-login-form"' in res.text and 'id="btn-admin-login"' in res.text, res.text[:200])
        check('admin login page masks password', 'type="password"' in res.text)
        check('admin login page links back to user login', 'href="/login"' in res.text)
        home = anon.get(f'{BASE_URL}/')
        check('home page visibly shows Admin link', 'id="nav-admin-login"' in home.text and '/admin/login' in home.text)
        login_page = anon.get(f'{BASE_URL}/login')
        check('user login page links to Admin Login', 'id="login-admin-link"' in login_page.text)

        # ---------- 2. Normal user access ----------
        print('2. Normal user access...')
        user = requests.Session()
        user.post(f'{BASE_URL}/api/register', json={
            'name': 'Extended Normal', 'email': user_email,
            'phone': '2223334444', 'password': 'password'
        })
        res = user.post(f'{BASE_URL}/api/login', json={'email': user_email, 'password': 'password'})
        check('normal user login', res.status_code == 200, res.text)

        res = user.get(f'{BASE_URL}/admin')
        check('normal user GET /admin -> 403', res.status_code == 403, res.status_code)
        for path in ('stats', 'stations', 'points', 'slots', 'bookings', 'users', 'notifications'):
            res = user.get(f'{BASE_URL}/api/admin/{path}')
            check(f'normal user GET /api/admin/{path} -> 403', res.status_code == 403, res.status_code)

        res = user.get(f'{BASE_URL}/dashboard')
        check('normal user GET /dashboard -> 200', res.status_code == 200, res.status_code)
        check('normal user dashboard hides Admin Panel link', 'id="nav-admin"' not in res.text)

        # ---------- 3. Admin access ----------
        print('3. Admin access...')
        admin = requests.Session()
        res = admin.post(f'{BASE_URL}/api/login', json={'email': admin_email, 'password': 'admin123'})
        check('admin login', res.status_code == 200, res.text)
        check('admin login reports is_admin', res.json()['user']['is_admin'] is True)
        check('login response has no password field', 'password' not in res.json()['user'])

        res = admin.get(f'{BASE_URL}/dashboard', allow_redirects=False)
        check('admin GET /dashboard redirects to /admin',
              res.status_code in (301, 302) and res.headers.get('Location', '').endswith('/admin'),
              f"{res.status_code} {res.headers.get('Location')}")

        res = admin.get(f'{BASE_URL}/admin')
        check('admin GET /admin -> 200', res.status_code == 200, res.status_code)
        check('admin page shows Admin Panel nav link', 'id="nav-admin"' in res.text)
        check('admin page has new stat cards',
              all(s in res.text for s in ('stat-active-sessions', 'stat-successful-payments', 'stat-failed-payments')))
        check('admin page has user search', 'id="user-search"' in res.text)
        check('admin page injects current admin id', 'const CURRENT_ADMIN_ID =' in res.text)

        # Admin login page behaviour for a signed-in admin
        res = admin.get(f'{BASE_URL}/admin/login', allow_redirects=False)
        check('signed-in admin visiting /admin/login redirects to /admin',
              res.status_code in (301, 302) and res.headers.get('Location', '').endswith('/admin'),
              f"{res.status_code} {res.headers.get('Location')}")

        # Logout must re-protect /admin (separate session so the main one stays usable)
        admin2 = requests.Session()
        res = admin2.post(f'{BASE_URL}/api/login', json={'email': admin_email, 'password': 'admin123'})
        check('second admin session login', res.status_code == 200, res.text)
        res = admin2.get(f'{BASE_URL}/admin', allow_redirects=False)
        check('admin2 can access /admin before logout', res.status_code == 200, res.status_code)
        res = admin2.post(f'{BASE_URL}/api/logout')
        check('admin logout succeeds', res.status_code == 200, res.status_code)
        res = admin2.get(f'{BASE_URL}/admin', allow_redirects=False)
        check('after logout, /admin requires admin login again',
              res.status_code in (301, 302) and '/admin/login' in res.headers.get('Location', ''),
              f"{res.status_code} {res.headers.get('Location')}")

        # Invalid credentials on the admin login API
        res = requests.post(f'{BASE_URL}/api/login', json={'email': admin_email, 'password': 'wrong-pass'})
        check('invalid admin credentials -> 401', res.status_code == 401, res.status_code)

        # ---------- 4. Statistics ----------
        print('4. Dashboard statistics...')
        res = admin.get(f'{BASE_URL}/api/admin/stats')
        check('stats endpoint -> 200', res.status_code == 200, res.text)
        stats = res.json()
        for key in ('total_users', 'total_stations', 'total_charging_points', 'total_bookings',
                    'active_bookings', 'active_sessions', 'completed_sessions', 'cancelled_bookings',
                    'successful_payments', 'failed_payments', 'revenue'):
            check(f'stats has numeric "{key}"', isinstance(stats.get(key), (int, float)), stats.get(key))

        # ---------- 5. Input validation ----------
        print('5. Input validation...')
        res = admin.post(f'{BASE_URL}/api/admin/stations', json={'name': 'Incomplete'})
        check('missing station fields -> 400 with error message',
              res.status_code == 400 and 'error' in res.json(), res.text)
        res = admin.post(f'{BASE_URL}/api/admin/stations', json={
            'name': 'Bad Price', 'location': 'X', 'operating_hours': '24/7',
            'connector_types': 'CCS', 'price_per_kwh': -1})
        check('negative price -> 400', res.status_code == 400 and 'non-negative' in res.json()['error'], res.text)
        res = admin.post(f'{BASE_URL}/api/admin/stations', json={
            'name': 'Bad Status', 'location': 'X', 'operating_hours': '24/7',
            'connector_types': 'CCS', 'price_per_kwh': 1, 'status': 'BROKEN'})
        check('invalid station status -> 400', res.status_code == 400 and 'status' in res.json()['error'], res.text)

        # ---------- 6. Station / point / slot CRUD ----------
        print('6. Station, point, and slot CRUD...')
        res = admin.post(f'{BASE_URL}/api/admin/stations', json={
            'name': TEST_STATION, 'location': 'Test Zone', 'operating_hours': '24/7',
            'connector_types': 'CCS', 'price_per_kwh': 0.9})
        check('create test station -> 201', res.status_code == 201, res.text)
        stations = admin.get(f'{BASE_URL}/api/admin/stations').json()
        station = next(s for s in stations if s['name'] == TEST_STATION)

        res = admin.post(f'{BASE_URL}/api/admin/points', json={
            'station_id': station['id'], 'point_name': 'Extended Point'})
        check('create test point -> 201', res.status_code == 201, res.text)
        points = admin.get(f'{BASE_URL}/api/admin/points').json()
        point = next(p for p in points if p['point_name'] == 'Extended Point')

        res = admin.post(f'{BASE_URL}/api/admin/points', json={
            'station_id': station['id'], 'point_name': 'Bad', 'status': 'WHATEVER'})
        check('invalid point status -> 400', res.status_code == 400 and 'status' in res.json()['error'], res.text)

        res = admin.post(f'{BASE_URL}/api/admin/slots', json={
            'point_id': point['id'], 'slot_time': '08:00-09:00'})
        check('create slot A -> 201', res.status_code == 201, res.text)
        res = admin.post(f'{BASE_URL}/api/admin/slots', json={
            'point_id': point['id'], 'slot_time': '08:00-09:00'})
        check('duplicate slot rejected -> 400', res.status_code == 400 and 'error' in res.json(), res.text)

        res = admin.post(f'{BASE_URL}/api/admin/slots', json={
            'point_id': point['id'], 'slot_time': '09:00-10:00'})
        check('create slot B -> 201', res.status_code == 201, res.text)
        slots = admin.get(f'{BASE_URL}/api/admin/slots').json()
        slot_a = next(s for s in slots if s['point_id'] == point['id'] and s['slot_time'] == '08:00-09:00')
        slot_b = next(s for s in slots if s['point_id'] == point['id'] and s['slot_time'] == '09:00-10:00')

        res = admin.put(f'{BASE_URL}/api/admin/slots/{slot_b["id"]}', json={
            'point_id': point['id'], 'slot_time': '08:00-09:00'})
        check('slot edit onto duplicate time -> 400', res.status_code == 400, res.text)
        res = admin.put(f'{BASE_URL}/api/admin/slots/{slot_b["id"]}', json={
            'point_id': point['id'], 'slot_time': '10:00-11:00'})
        check('slot edit to free time -> 200', res.status_code == 200, res.text)

        # ---------- 7. Cascade delete for booking-free station ----------
        print('7. Cascade delete...')
        res = admin.post(f'{BASE_URL}/api/admin/stations', json={
            'name': 'Cascade Temp Station', 'location': 'Tmp', 'operating_hours': '24/7',
            'connector_types': 'CCS', 'price_per_kwh': 0.5})
        check('create cascade station -> 201', res.status_code == 201, res.text)
        stations = admin.get(f'{BASE_URL}/api/admin/stations').json()
        cascade_station = next(s for s in stations if s['name'] == 'Cascade Temp Station')
        admin.post(f'{BASE_URL}/api/admin/points', json={
            'station_id': cascade_station['id'], 'point_name': 'Cascade Point'})
        points = admin.get(f'{BASE_URL}/api/admin/points').json()
        cascade_point = next(p for p in points if p['point_name'] == 'Cascade Point')
        res = admin.delete(f'{BASE_URL}/api/admin/stations/{cascade_station["id"]}')
        check('booking-free station deletes with cascade -> 200', res.status_code == 200, res.text)
        points = admin.get(f'{BASE_URL}/api/admin/points').json()
        check('cascade removed its charging points',
              all(p['id'] != cascade_point['id'] for p in points))

        # ---------- 8. Booking lifecycle via normal user ----------
        print('8. Booking lifecycle and admin guards...')
        res = user.post(f'{BASE_URL}/api/bookings', json={'slot_id': slot_a['id'], 'date': TEST_DATE})
        check('user creates booking -> 201', res.status_code == 201, res.text)
        booking_a = res.json()['booking_id']

        res = user.post(f'{BASE_URL}/api/bookings', json={'slot_id': slot_b['id'], 'date': TEST_DATE})
        check('user creates second booking -> 201', res.status_code == 201, res.text)
        booking_b = res.json()['booking_id']

        res = admin.delete(f'{BASE_URL}/api/admin/users/999999')
        check('deleting unknown user -> 404', res.status_code == 404, res.status_code)
        users = admin.get(f'{BASE_URL}/api/admin/users').json()
        normal_id = next(u['id'] for u in users if u['email'] == user_email)
        res = admin.delete(f'{BASE_URL}/api/admin/users/{normal_id}')
        check('user with active bookings cannot be deleted -> 400',
              res.status_code == 400 and 'active booking' in res.json()['error'], res.text)

        # Booking filters
        res = admin.get(f'{BASE_URL}/api/admin/bookings')
        all_bookings = res.json()
        check('bookings include payment_status field',
              all('payment_status' in b for b in all_bookings))
        res = admin.get(f'{BASE_URL}/api/admin/bookings', params={'search': booking_a})
        found = res.json()
        check('booking search by id returns only that booking',
              len(found) == 1 and found[0]['id'] == booking_a, res.text)
        res = admin.get(f'{BASE_URL}/api/admin/bookings', params={'status': 'PENDING'})
        check('booking status filter returns only PENDING',
              all(b['status'] == 'PENDING' for b in res.json()) and
              any(b['id'] == booking_a for b in res.json()), res.text)
        res = admin.get(f'{BASE_URL}/api/admin/bookings', params={'status': 'NO_SUCH_STATUS'})
        check('unknown booking status filter returns empty list', res.json() == [], res.text)

        # Invalid status transitions
        res = admin.put(f'{BASE_URL}/api/admin/bookings/{booking_a}/status',
                        json={'status': 'COMPLETED'})
        check('unsafe status change rejected -> 400', res.status_code == 400 and 'error' in res.json(), res.text)
        res = admin.put(f'{BASE_URL}/api/admin/bookings/BKGNOTEXIST/status',
                        json={'status': 'CANCELLED'})
        check('status change on unknown booking -> 404', res.status_code == 404, res.status_code)

        # Cancel the PENDING booking as admin
        res = admin.put(f'{BASE_URL}/api/admin/bookings/{booking_b}/status',
                        json={'status': 'CANCELLED'})
        check('admin cancels PENDING booking -> 200', res.status_code == 200, res.text)
        res = admin.get(f'{BASE_URL}/api/admin/bookings', params={'search': booking_b})
        check('cancelled booking persisted as CANCELLED',
              res.json()[0]['status'] == 'CANCELLED', res.text)
        res = admin.put(f'{BASE_URL}/api/admin/bookings/{booking_b}/status',
                        json={'status': 'CANCELLED'})
        check('re-cancelling a cancelled booking -> 400', res.status_code == 400, res.status_code)

        notifs = user.get(f'{BASE_URL}/api/notifications').json()
        check('user notified of admin cancellation',
              any('cancelled by the administrator' in n['message'] for n in notifs), notifs)

        # ---------- 9. Charging session guard ----------
        print('9. Charging session guard...')
        res = user.post(f'{BASE_URL}/api/payments', json={'booking_id': booking_a, 'method': 'CREDIT_CARD'})
        check('payment succeeds -> 201', res.status_code == 201, res.text)
        res = user.post(f'{BASE_URL}/api/charging/start', json={'booking_id': booking_a})
        check('charging starts -> 200', res.status_code == 200, res.text)

        res = admin.put(f'{BASE_URL}/api/admin/points/{point["id"]}', json={
            'station_id': station['id'], 'point_name': point['point_name'], 'status': 'INACTIVE'})
        check('deactivating point during active charging -> 400',
              res.status_code == 400 and 'charging session' in res.json()['error'], res.text)

        res = user.post(f'{BASE_URL}/api/charging/complete', json={'booking_id': booking_a})
        check('charging completes -> 200', res.status_code == 200, res.text)
        res = admin.put(f'{BASE_URL}/api/admin/bookings/{booking_a}/status',
                        json={'status': 'CANCELLED'})
        check('cancelling a COMPLETED booking -> 400', res.status_code == 400, res.status_code)
        res = admin.put(f'{BASE_URL}/api/admin/points/{point["id"]}', json={
            'station_id': station['id'], 'point_name': point['point_name'], 'status': 'INACTIVE'})
        check('point deactivates once session finished -> 200', res.status_code == 200, res.text)

        # ---------- 10. Referenced data cannot be deleted ----------
        print('10. Referenced data protection...')
        res = admin.delete(f'{BASE_URL}/api/admin/slots/{slot_a["id"]}')
        check('slot with bookings cannot be deleted -> 400', res.status_code == 400, res.status_code)
        res = admin.delete(f'{BASE_URL}/api/admin/points/{point["id"]}')
        check('point with bookings cannot be deleted -> 400', res.status_code == 400, res.status_code)
        res = admin.delete(f'{BASE_URL}/api/admin/stations/{station["id"]}')
        check('station with bookings cannot be deleted -> 400', res.status_code == 400, res.status_code)

        # ---------- 11. User management ----------
        print('11. User management...')
        res = admin.post(f'{BASE_URL}/api/register', json={
            'name': 'Doomed User', 'email': doomed_email,
            'phone': '3334445555', 'password': 'password'})
        check('register doomed user', res.status_code in (201, 400), res.text)
        res = admin.get(f'{BASE_URL}/api/admin/users', params={'search': 'ext_doomed'})
        found = res.json()
        check('user search finds the new user', len(found) == 1 and found[0]['email'] == doomed_email, res.text)
        check('admin users never expose passwords',
              all('password' not in u for u in found) and all('password' not in u for u in users))
        doomed_id = found[0]['id']

        res = admin.delete(f'{BASE_URL}/api/admin/users/{doomed_id}')
        check('deleting booking-free user -> 200', res.status_code == 200, res.text)
        res = admin.get(f'{BASE_URL}/api/admin/users', params={'search': 'ext_doomed'})
        check('deleted user no longer listed', res.json() == [], res.text)

        admin_id = next(u['id'] for u in admin.get(f'{BASE_URL}/api/admin/users').json()
                        if u['email'] == admin_email)
        res = admin.delete(f'{BASE_URL}/api/admin/users/{admin_id}')
        check('admin cannot delete own account -> 400',
              res.status_code == 400 and 'own administrator account' in res.json()['error'], res.text)

        # ---------- 12. Pricing persistence ----------
        print('12. Pricing persistence...')
        res = admin.put(f'{BASE_URL}/api/admin/stations/{station["id"]}', json={
            'name': TEST_STATION, 'location': 'Test Zone', 'operating_hours': '24/7',
            'connector_types': 'CCS', 'price_per_kwh': 1.25, 'status': 'ACTIVE'})
        check('pricing update -> 200', res.status_code == 200, res.text)
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute('SELECT price_per_kwh FROM stations WHERE id = ?', (station['id'],)).fetchone()
        conn.close()
        check('pricing persisted in SQLite', row is not None and abs(row[0] - 1.25) < 1e-9, row)
        res = admin.put(f'{BASE_URL}/api/admin/stations/{station["id"]}', json={
            'name': TEST_STATION, 'location': 'Test Zone', 'operating_hours': '24/7',
            'connector_types': 'CCS', 'price_per_kwh': -5, 'status': 'ACTIVE'})
        check('negative pricing update -> 400', res.status_code == 400, res.status_code)

        print('Extended admin tests completed successfully!')
    finally:
        cleanup_database(test_emails, TEST_STATION)
        cleanup_database([doomed_email], 'Cascade Temp Station')


if __name__ == '__main__':
    time.sleep(1)
    try:
        test_admin_extended()
    except AssertionError as e:
        print(f'Test failed: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'Test failed with unexpected error: {e}')
        sys.exit(1)





