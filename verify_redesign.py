"""Temporary end-to-end verification for the UI redesign + admin module."""
import datetime

import requests

BASE = 'http://localhost:5000'
results = []


def check(name, cond, extra=''):
    results.append((name, bool(cond)))
    print(('PASS' if cond else 'FAIL'), '-', name, ('| ' + str(extra) if (extra and not cond) else ''))


# ---------- 1. Public pages ----------
pub = requests.Session()
for path in ['/', '/login', '/register', '/stations', '/stations/1', '/book/1']:
    try:
        r = pub.get(BASE + path, timeout=10)
        check(f'GET {path} -> 200', r.status_code == 200, r.status_code)
    except Exception as e:
        check(f'GET {path}', False, e)

for path in ['/static/css/style.css', '/static/js/main.js']:
    r = pub.get(BASE + path)
    check(f'GET {path} -> 200', r.status_code == 200)

# ---------- 2. Page IDs (Selenium compatibility) ----------
login_html = pub.get(BASE + '/login').text
for i in ['id="login-form"', 'id="email"', 'id="password"', 'id="btn-login"']:
    check(f'login has {i}', i in login_html)
for c in ['login-email', 'login-password', 'login-button']:
    check(f'login exposes spec name/class {c}', c in login_html)
check('base has toast container', 'toast-container' in login_html)
check('base has footer', 'footer' in login_html)

reg_html = pub.get(BASE + '/register').text
for i in ['id="register-form"', 'id="name"', 'id="phone"', 'id="btn-register"']:
    check(f'register has {i}', i in reg_html)
for c in ['register-name', 'register-email', 'register-password', 'register-button']:
    check(f'register exposes spec name/class {c}', c in reg_html)

check('nav-login id', 'id="nav-login"' in login_html)
check('nav-register id', 'id="nav-register"' in login_html)

# ---------- 3. User registration + login ----------
user = requests.Session()
uemail = 'redesign_test@example.com'
user.post(BASE + '/api/register', json={'name': 'Redesign Test', 'email': uemail,
                                        'phone': '9998887776', 'password': 'testpass'})
r = user.post(BASE + '/api/login', json={'email': uemail, 'password': 'testpass'})
check('user login', r.status_code == 200, r.text)
uid = r.json()['user']['id']

dash = user.get(BASE + '/dashboard').text
for i in ['btn-goto-stations', 'btn-goto-history', 'stat-total-bookings', 'dash-recent-bookings']:
    check(f'dashboard has {i}', i in dash)
check('nav-notifications id', 'id="nav-notifications"' in dash)
check('logout-btn id', 'id="logout-btn"' in dash)

st = user.get(BASE + '/stations').text
for i in ['id="search-input"', 'id="btn-search"', 'id="stations-list"', 'id="station-filter"']:
    check(f'stations has {i}', i in st)
check('stations exposes station-search', 'station-search' in st)

sd = user.get(BASE + '/stations/1').text
for i in ['id="station-name"', 'id="station-location"', 'id="booking-date"',
          'id="btn-load-slots"', 'id="slots-table-body"']:
    check(f'station details has {i}', i in sd)
check('station details booking-slot class', 'booking-slot' in sd)
check('station details booking-button class', 'booking-button' in sd)

hist = user.get(BASE + '/history').text
for i in ['id="history-table-body"', 'history-stat-upcoming']:
    check(f'history has {i}', i in hist)

notif = user.get(BASE + '/notifications').text
check('notifications has table body', 'id="notifications-table-body"' in notif)

bk = user.get(BASE + '/book/1').text
for i in ['id="booking-slot"', 'id="booking-date"', 'id="booking-button"', 'id="book-form"']:
    check(f'book page has {i}', i in bk)

r = user.get(BASE + '/admin')
check('non-admin /admin does not show Admin Dashboard', 'Admin Dashboard' not in r.text)
# ---------- 4. Full booking workflow ----------
r = user.get(BASE + '/api/stations', params={'search': 'Central'})
check('station search works', r.status_code == 200 and len(r.json()) >= 1)

r = user.get(BASE + '/api/stations')
all_stations = r.json()
avail, book_date = None, None
for offset in range(14):
    d = (datetime.date(2026, 10, 20) + datetime.timedelta(days=offset)).isoformat()
    for st in all_stations:
        slots = user.get(BASE + f"/api/stations/{st['id']}/slots", params={'date': d}).json()
        avail = next((s for s in slots if s['is_available']), None)
        if avail:
            book_date = d
            break
    if avail:
        break
check('slot availability works', avail is not None)

r = user.post(BASE + '/api/bookings', json={'slot_id': avail['id'], 'date': book_date})
check('booking created', r.status_code == 201, r.text)
bid = r.json()['booking_id']

pay = user.get(BASE + f'/payment/{bid}').text
for i in ['id="booking-id-display"', 'id="amount-display"', 'id="payment-method"', 'id="btn-pay"']:
    check(f'payment page has {i}', i in pay)
check('payment exposes payment-button', 'payment-button' in pay)
# ---------- 5. Admin module (continued in next marker) ----------
r = user.post(BASE + '/api/payments', json={'booking_id': bid, 'method': 'FAIL'})
check('payment failure path (400)', r.status_code == 400)
r = user.post(BASE + '/api/payments', json={'booking_id': bid, 'method': 'CREDIT_CARD'})
check('payment success path (201)', r.status_code == 201)

r = user.post(BASE + '/api/charging/start', json={'booking_id': bid})
check('charging start', r.status_code == 200)
r = user.post(BASE + '/api/charging/complete', json={'booking_id': bid})
check('charging complete', r.status_code == 200)

r = user.get(BASE + '/api/stations/1/slots', params={'date': '2026-11-15'})
avail2 = next((s for s in r.json() if s['is_available']), None)
check('second slot available', avail2 is not None)
r = user.post(BASE + '/api/bookings', json={'slot_id': avail2['id'], 'date': '2026-11-15'})
check('second booking created', r.status_code == 201 and 'booking_id' in r.json(), r.text)
bid2 = r.json().get('booking_id')
r = user.put(BASE + f'/api/bookings/{bid2}/cancel')
check('cancellation', r.status_code == 200)

r = user.get(BASE + f'/api/users/{uid}/bookings')
check('booking history API', r.status_code == 200 and len(r.json()) >= 2)

r = user.get(BASE + '/api/notifications')
check('notifications API', r.status_code == 200 and len(r.json()) >= 1)
# == ADMIN CHECKS ==
admin = requests.Session()
r = admin.post(BASE + '/api/login', json={'email': 'admin@example.com', 'password': 'admin123'})
check('admin login', r.status_code == 200)

adm = admin.get(BASE + '/admin').text
check('admin page renders', 'Admin Dashboard' in adm)
for i in ['id="admin-dashboard"', 'id="admin-stations"', 'id="admin-charging-points"',
          'id="admin-slots"', 'id="admin-pricing"', 'id="admin-bookings"',
          'id="admin-users"', 'id="admin-notifications"',
          'id="admin-stations-list"', 'id="admin-points-list"', 'id="admin-slots-list"',
          'id="admin-bookings-list"', 'id="admin-users-list"', 'id="admin-notifications-list"',
          'id="pricing-list"', 'id="recent-bookings-list"', 'id="slot-availability-date"',
          'id="btn-add-station-toggle"', 'id="add-station-form"', 'id="station-price"',
          'id="point-status"', 'id="admin-modal"', 'id="stat-revenue"']:
    check(f'admin has {i}', i in adm)
check('admin shows INR entity', '&#8377;' in adm)
check('admin spec class admin-add-station', 'admin-add-station' in adm)

r = admin.get(BASE + '/api/admin/stats')
check('stats endpoint', r.status_code == 200 and 'revenue' in r.json(), r.text[:200])
r = admin.get(BASE + '/api/admin/users')
check('users endpoint, no passwords',
      r.status_code == 200 and len(r.json()) > 0 and all('password' not in u for u in r.json()))
r = admin.get(BASE + '/api/admin/notifications')
check('admin notifications endpoint', r.status_code == 200)
r = admin.get(BASE + '/api/admin/slots/availability', params={'date': '2026-10-20'})
check('availability endpoint', r.status_code == 200 and len(r.json()) > 0)
r = admin.get(BASE + '/api/admin/bookings')
check('bookings include payment_status',
      r.status_code == 200 and all('payment_status' in b for b in r.json()))

r = admin.post(BASE + '/api/admin/stations', json={'name': 'Verify Station', 'location': 'Test Zone',
                                                   'operating_hours': '24/7', 'connector_types': 'CCS',
                                                   'price_per_kwh': 0.9})
check('admin add station', r.status_code == 201, r.text)
stations = admin.get(BASE + '/api/admin/stations').json()
vs = next(s for s in stations if s['name'] == 'Verify Station')
r = admin.put(BASE + f"/api/admin/stations/{vs['id']}",
              json={'name': 'Verify Station 2', 'location': 'Test Zone', 'operating_hours': '24/7',
                    'connector_types': 'CCS', 'price_per_kwh': 1.1, 'status': 'ACTIVE'})
check('admin edit station', r.status_code == 200)

r = admin.post(BASE + '/api/admin/points', json={'station_id': vs['id'], 'point_name': 'Verify Point',
                                                 'status': 'INACTIVE'})
check('admin add point with status', r.status_code == 201, r.text)
points = admin.get(BASE + '/api/admin/points').json()
vp = next(p for p in points if p['point_name'] == 'Verify Point')
check('point status persisted', vp.get('status') == 'INACTIVE', vp)
r = admin.put(BASE + f"/api/admin/points/{vp['id']}",
              json={'station_id': vp['station_id'], 'point_name': vp['point_name'], 'status': 'ACTIVE'})
check('admin edit point status', r.status_code == 200)
r = admin.put(BASE + f"/api/admin/points/{vp['id']}",
              json={'station_id': vp['station_id'], 'point_name': vp['point_name']})
check('admin edit point legacy payload (no status)', r.status_code == 200)

r = admin.post(BASE + '/api/admin/slots', json={'point_id': vp['id'], 'slot_time': '22:00-23:00'})
check('admin add slot', r.status_code == 201, r.text)
aslots = admin.get(BASE + '/api/admin/slots').json()
vsl = next(s for s in aslots if s['point_id'] == vp['id'] and s['slot_time'] == '22:00-23:00')
r = admin.put(BASE + f"/api/admin/slots/{vsl['id']}",
              json={'point_id': vp['id'], 'slot_time': '22:30-23:30'})
check('admin edit slot', r.status_code == 200)

r = user.get(BASE + '/api/admin/stats')
check('non-admin blocked from admin API (403)', r.status_code == 403)

import sqlite3
conn = sqlite3.connect(r'd:\EV-Charging-Station\database\ev_booking.db')
cols = [row[1] for row in conn.execute('PRAGMA table_info(charging_points)')]
conn.close()
check('charging_points.status column migrated', 'status' in cols, cols)

admin.delete(BASE + f"/api/admin/slots/{vsl['id']}")
admin.delete(BASE + f"/api/admin/points/{vp['id']}")
admin.delete(BASE + f"/api/admin/stations/{vs['id']}")


# cleanup stray debug booking (slot on 2026-10-21) if still open
for b in user.get(BASE + f'/api/users/{uid}/bookings').json():
    if b['date'] == '2026-10-21' and b['status'] in ('PENDING', 'CONFIRMED'):
        user.put(BASE + f"/api/bookings/{b['id']}/cancel")

# ---------- summary ----------
fails = [n for n, ok in results if not ok]
print(f"\n==== {len(results) - len(fails)}/{len(results)} CHECKS PASSED ====")
if fails:
    print('FAILED:')
    for f in fails:
        print(' -', f)
    raise SystemExit(1)
print('ALL CHECKS PASSED')
