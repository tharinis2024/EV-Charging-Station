from flask import Blueprint, request, jsonify, session
from database.db import get_db

admin_api = Blueprint('admin_api', __name__)

def is_admin():
    return session.get('is_admin') == 1 or session.get('is_admin') is True

@admin_api.before_request
def check_admin():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized: Login required'}), 401
    if not is_admin():
        return jsonify({'error': 'Forbidden: Admin access required'}), 403

# Allowed status values shared by stations and charging points
VALID_STATUSES = ('ACTIVE', 'INACTIVE')


def _validate_status(status):
    """Return an error message if status is not a known value, else None."""
    if status not in VALID_STATUSES:
        return f"status must be one of: {', '.join(VALID_STATUSES)}"
    return None


# === DASHBOARD STATISTICS ===
@admin_api.route('/stats', methods=['GET'])
def get_stats():
    conn = get_db()

    def count(query, params=()):
        return conn.execute(query, params).fetchone()[0]

    stats = {
        'total_users': count('SELECT COUNT(*) FROM users'),
        'total_stations': count('SELECT COUNT(*) FROM stations'),
        'total_charging_points': count('SELECT COUNT(*) FROM charging_points'),
        'total_bookings': count('SELECT COUNT(*) FROM bookings'),
        'active_bookings': count("SELECT COUNT(*) FROM bookings WHERE status IN ('PENDING','CONFIRMED','CHARGING')"),
        'active_sessions': count("SELECT COUNT(*) FROM charging_sessions WHERE status = 'CHARGING'"),
        'completed_sessions': count("SELECT COUNT(*) FROM bookings WHERE status = 'COMPLETED'"),
        'cancelled_bookings': count("SELECT COUNT(*) FROM bookings WHERE status = 'CANCELLED'"),
        'successful_payments': count("SELECT COUNT(*) FROM payments WHERE status = 'SUCCESS'"),
        'failed_payments': count("SELECT COUNT(*) FROM payments WHERE status = 'FAILED'"),
        'revenue': count("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'SUCCESS'")
    }
    conn.close()
    return jsonify(stats), 200


# === STATIONS ===
@admin_api.route('/stations', methods=['GET'])
def get_stations():
    conn = get_db()
    stations = conn.execute('SELECT * FROM stations').fetchall()
    conn.close()
    return jsonify([dict(s) for s in stations]), 200

@admin_api.route('/stations', methods=['POST'])
def add_station():
    data = request.json or {}
    required = ['name', 'location', 'operating_hours', 'connector_types', 'price_per_kwh']
    missing = [f for f in required if not data.get(f) and data.get(f) != 0]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    try:
        price = float(data['price_per_kwh'])
        if price < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'error': 'price_per_kwh must be a non-negative number'}), 400

    status = data.get('status', 'ACTIVE')
    status_error = _validate_status(status)
    if status_error:
        return jsonify({'error': status_error}), 400

    conn = get_db()
    conn.execute('''
        INSERT INTO stations (name, location, operating_hours, connector_types, price_per_kwh, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (data['name'], data['location'], data['operating_hours'],
          data['connector_types'], price, status))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Station added successfully'}), 201

@admin_api.route('/stations/<int:id>', methods=['PUT'])
def edit_station(id):
    data = request.json or {}
    required = ['name', 'location', 'operating_hours', 'connector_types', 'price_per_kwh', 'status']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    try:
        price = float(data['price_per_kwh'])
        if price < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'error': 'price_per_kwh must be a non-negative number'}), 400

    status_error = _validate_status(data['status'])
    if status_error:
        return jsonify({'error': status_error}), 400

    conn = get_db()
    station = conn.execute('SELECT id FROM stations WHERE id = ?', (id,)).fetchone()
    if not station:
        conn.close()
        return jsonify({'error': 'Station not found'}), 404

    conn.execute('''
        UPDATE stations SET name=?, location=?, operating_hours=?, connector_types=?, price_per_kwh=?, status=?
        WHERE id=?
    ''', (data['name'], data['location'], data['operating_hours'],
          data['connector_types'], price, data['status'], id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Station updated successfully'}), 200

@admin_api.route('/stations/<int:id>', methods=['DELETE'])
def delete_station(id):
    conn = get_db()
    # A station may only be removed when no bookings (active or historical)
    # reference any of its slots — history pages JOIN through slots/points.
    referenced = conn.execute('''
        SELECT COUNT(*) FROM bookings b
        JOIN slots s ON b.slot_id = s.id
        JOIN charging_points p ON s.point_id = p.id
        WHERE p.station_id = ?
    ''', (id,)).fetchone()[0]

    if referenced > 0:
        conn.close()
        return jsonify({'error': f'Cannot delete station: {referenced} booking(s) reference it. Historical bookings must stay intact.'}), 400

    try:
        # No bookings reference this station: cascade-delete its slots,
        # charging points, and finally the station itself, atomically.
        conn.execute('''
            DELETE FROM slots WHERE point_id IN (SELECT id FROM charging_points WHERE station_id = ?)
        ''', (id,))
        conn.execute('DELETE FROM charging_points WHERE station_id = ?', (id,))
        deleted = conn.execute('DELETE FROM stations WHERE id = ?', (id,)).rowcount
        if not deleted:
            conn.rollback()
            conn.close()
            return jsonify({'error': 'Station not found'}), 404
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Failed to delete station: {e}'}), 500
    conn.close()
    return jsonify({'message': 'Station deleted successfully'}), 200


# === CHARGING POINTS ===
@admin_api.route('/points', methods=['GET'])
def get_points():
    conn = get_db()
    points = conn.execute('''
        SELECT p.*, s.name as station_name
        FROM charging_points p JOIN stations s ON p.station_id = s.id
    ''').fetchall()
    conn.close()
    return jsonify([dict(p) for p in points]), 200

@admin_api.route('/points', methods=['POST'])
def add_point():
    data = request.json or {}
    if not data.get('station_id') or not data.get('point_name', '').strip():
        return jsonify({'error': 'station_id and point_name are required'}), 400

    status = data.get('status', 'ACTIVE')
    status_error = _validate_status(status)
    if status_error:
        return jsonify({'error': status_error}), 400

    conn = get_db()
    station = conn.execute('SELECT id FROM stations WHERE id = ?', (data['station_id'],)).fetchone()
    if not station:
        conn.close()
        return jsonify({'error': 'Station not found'}), 404

    conn.execute('INSERT INTO charging_points (station_id, point_name, status) VALUES (?, ?, ?)',
                 (data['station_id'], data['point_name'].strip(), status))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Charging point added'}), 201

@admin_api.route('/points/<int:id>', methods=['PUT'])
def edit_point(id):
    data = request.json or {}
    if 'station_id' not in data or 'point_name' not in data:
        return jsonify({'error': 'station_id and point_name are required'}), 400

    conn = get_db()
    point = conn.execute('SELECT id FROM charging_points WHERE id = ?', (id,)).fetchone()
    if not point:
        conn.close()
        return jsonify({'error': 'Charging point not found'}), 404

    if 'status' in data:
        status_error = _validate_status(data['status'])
        if status_error:
            conn.close()
            return jsonify({'error': status_error}), 400

        if data['status'] == 'INACTIVE':
            # Refuse to deactivate while one of its slots is charging right now.
            charging = conn.execute('''
                SELECT COUNT(*) FROM bookings b
                JOIN slots s ON b.slot_id = s.id
                WHERE s.point_id = ? AND b.status = 'CHARGING'
            ''', (id,)).fetchone()[0]
            if charging > 0:
                conn.close()
                return jsonify({'error': f'Cannot deactivate this charging point: {charging} charging session(s) are in progress.'}), 400

        conn.execute('UPDATE charging_points SET station_id=?, point_name=?, status=? WHERE id=?',
                     (data['station_id'], data['point_name'], data['status'], id))
    else:
        conn.execute('UPDATE charging_points SET station_id=?, point_name=? WHERE id=?',
                     (data['station_id'], data['point_name'], id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Charging point updated'}), 200

@admin_api.route('/points/<int:id>', methods=['DELETE'])
def delete_point(id):
    conn = get_db()
    # Bookings (active or historical) must never lose their charging point/slot chain.
    referenced = conn.execute('''
        SELECT COUNT(*) FROM bookings b
        JOIN slots s ON b.slot_id = s.id
        WHERE s.point_id = ?
    ''', (id,)).fetchone()[0]

    if referenced > 0:
        conn.close()
        return jsonify({'error': f'Cannot delete point: {referenced} booking(s) reference its slots.'}), 400

    try:
        conn.execute('DELETE FROM slots WHERE point_id = ?', (id,))
        deleted = conn.execute('DELETE FROM charging_points WHERE id=?', (id,)).rowcount
        if not deleted:
            conn.rollback()
            conn.close()
            return jsonify({'error': 'Charging point not found'}), 404
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Failed to delete charging point: {e}'}), 500
    conn.close()
    return jsonify({'message': 'Charging point deleted successfully'}), 200


# === SLOTS ===
@admin_api.route('/slots', methods=['GET'])
def get_slots():
    conn = get_db()
    slots = conn.execute('''
        SELECT sl.*, p.point_name, s.name as station_name
        FROM slots sl
        JOIN charging_points p ON sl.point_id = p.id
        JOIN stations s ON p.station_id = s.id
    ''').fetchall()
    conn.close()
    return jsonify([dict(s) for s in slots]), 200

@admin_api.route('/slots', methods=['POST'])
def add_slot():
    data = request.json or {}
    if not data.get('point_id') or not data.get('slot_time', '').strip():
        return jsonify({'error': 'point_id and slot_time are required'}), 400

    conn = get_db()
    point = conn.execute('SELECT id FROM charging_points WHERE id = ?', (data['point_id'],)).fetchone()
    if not point:
        conn.close()
        return jsonify({'error': 'Charging point not found'}), 404

    duplicate = conn.execute('SELECT id FROM slots WHERE point_id = ? AND slot_time = ?',
                             (data['point_id'], data['slot_time'].strip())).fetchone()
    if duplicate:
        conn.close()
        return jsonify({'error': 'A slot with this time already exists for this charging point'}), 400

    conn.execute('INSERT INTO slots (point_id, slot_time) VALUES (?, ?)',
                 (data['point_id'], data['slot_time'].strip()))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Slot added'}), 201

@admin_api.route('/slots/<int:id>', methods=['PUT'])
def edit_slot(id):
    data = request.json or {}
    if 'point_id' not in data or 'slot_time' not in data:
        return jsonify({'error': 'point_id and slot_time are required'}), 400

    conn = get_db()
    slot = conn.execute('SELECT id FROM slots WHERE id = ?', (id,)).fetchone()
    if not slot:
        conn.close()
        return jsonify({'error': 'Slot not found'}), 404

    duplicate = conn.execute('SELECT id FROM slots WHERE point_id = ? AND slot_time = ? AND id != ?',
                             (data['point_id'], data['slot_time'], id)).fetchone()
    if duplicate:
        conn.close()
        return jsonify({'error': 'A slot with this time already exists for this charging point'}), 400

    conn.execute('UPDATE slots SET point_id=?, slot_time=? WHERE id=?',
                 (data['point_id'], data['slot_time'], id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Slot updated'}), 200

@admin_api.route('/slots/<int:id>', methods=['DELETE'])
def delete_slot(id):
    conn = get_db()
    # Any booking — including completed/cancelled history — keeps the slot alive.
    referenced = conn.execute(
        'SELECT COUNT(*) FROM bookings WHERE slot_id = ?',
        (id,)
    ).fetchone()[0]

    if referenced > 0:
        conn.close()
        return jsonify({'error': f'Cannot delete slot: {referenced} booking(s) reference it. Historical bookings must stay intact.'}), 400

    deleted = conn.execute('DELETE FROM slots WHERE id=?', (id,)).rowcount
    if not deleted:
        conn.close()
        return jsonify({'error': 'Slot not found'}), 404
    conn.commit()
    conn.close()
    return jsonify({'message': 'Slot deleted successfully'}), 200


# === BOOKINGS ===
@admin_api.route('/bookings', methods=['GET'])
def get_bookings():
    # Optional server-side filters: /api/admin/bookings?status=PENDING&search=BKG
    status = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()

    where = []
    params = []
    if status:
        where.append('b.status = ?')
        params.append(status)
    if search:
        where.append('(b.id LIKE ? OR u.name LIKE ? OR u.email LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    conn = get_db()
    bookings = conn.execute(f'''
        SELECT b.*, u.name as user_name, u.email as user_email, s.slot_time, p.point_name, st.name as station_name,
               (SELECT pm.status FROM payments pm WHERE pm.booking_id = b.id
                ORDER BY pm.transaction_date DESC, pm.id DESC LIMIT 1) as payment_status,
               (SELECT pm.method FROM payments pm WHERE pm.booking_id = b.id
                ORDER BY pm.transaction_date DESC, pm.id DESC LIMIT 1) as payment_method
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN slots s ON b.slot_id = s.id
        JOIN charging_points p ON s.point_id = p.id
        JOIN stations st ON p.station_id = st.id
        {where_sql}
        ORDER BY b.date DESC
    ''', params).fetchall()
    conn.close()
    return jsonify([dict(b) for b in bookings]), 200


# === BOOKING STATUS (safe admin transitions only) ===
@admin_api.route('/bookings/<id>/status', methods=['PUT'])
def update_booking_status(id):
    data = request.json or {}
    new_status = (data.get('status') or '').upper().strip()

    if new_status != 'CANCELLED':
        return jsonify({'error': 'Only cancelling a booking is allowed from the admin panel (status must be CANCELLED).'}), 400

    conn = get_db()
    booking = conn.execute('SELECT * FROM bookings WHERE id = ?', (id,)).fetchone()
    if not booking:
        conn.close()
        return jsonify({'error': 'Booking not found'}), 404

    if booking['status'] in ('COMPLETED', 'CANCELLED'):
        conn.close()
        return jsonify({'error': f'Cannot cancel a {booking["status"]} booking'}), 400

    try:
        conn.execute('UPDATE bookings SET status = ? WHERE id = ?', (new_status, id))
        conn.execute('UPDATE charging_sessions SET status = ? WHERE booking_id = ?', (new_status, id))
        conn.execute('INSERT INTO notifications (user_id, message) VALUES (?, ?)',
                     (booking['user_id'], f'Booking {id} has been cancelled by the administrator.'))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Failed to update booking: {e}'}), 500
    conn.close()
    return jsonify({'message': f'Booking {id} cancelled successfully'}), 200


# === USER MANAGEMENT (passwords are never selected) ===
@admin_api.route('/users', methods=['GET'])
def get_users():
    # Optional server-side search: /api/admin/users?search=example
    search = request.args.get('search', '').strip()
    where_sql = ''
    params = []
    if search:
        where_sql = 'WHERE (u.name LIKE ? OR u.email LIKE ? OR u.phone LIKE ?)'
        params = [f'%{search}%', f'%{search}%', f'%{search}%']

    conn = get_db()
    users = conn.execute(f'''
        SELECT u.id, u.name, u.email, u.phone, u.is_admin,
               COUNT(b.id) AS booking_count,
               COALESCE(SUM(CASE WHEN b.status = 'CANCELLED' THEN 1 ELSE 0 END), 0) AS cancelled_count
        FROM users u
        LEFT JOIN bookings b ON b.user_id = u.id
        {where_sql}
        GROUP BY u.id
        ORDER BY u.id
    ''', params).fetchall()
    conn.close()
    return jsonify([dict(u) for u in users]), 200


@admin_api.route('/users/<int:id>', methods=['DELETE'])
def delete_user(id):
    # Never let an admin remove the account they are signed in with.
    if id == session.get('user_id'):
        return jsonify({'error': 'You cannot delete your own administrator account.'}), 400

    conn = get_db()
    user = conn.execute('SELECT id, name FROM users WHERE id = ?', (id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    active = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE user_id = ? AND status NOT IN ('CANCELLED', 'COMPLETED')",
        (id,)
    ).fetchone()[0]
    if active > 0:
        conn.close()
        return jsonify({'error': f'Cannot delete user: {active} active booking(s) belong to this account.'}), 400

    try:
        # Remove the user's notifications, payments, bookings, then the account.
        conn.execute('DELETE FROM notifications WHERE user_id = ?', (id,))
        conn.execute('DELETE FROM payments WHERE booking_id IN (SELECT id FROM bookings WHERE user_id = ?)', (id,))
        conn.execute('DELETE FROM charging_sessions WHERE booking_id IN (SELECT id FROM bookings WHERE user_id = ?)', (id,))
        conn.execute('DELETE FROM bookings WHERE user_id = ?', (id,))
        conn.execute('DELETE FROM users WHERE id = ?', (id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Failed to delete user: {e}'}), 500
    conn.close()
    return jsonify({'message': f"User '{user['name']}' deleted successfully"}), 200


# === ADMIN NOTIFICATIONS ===
@admin_api.route('/notifications', methods=['GET'])
def get_all_notifications():
    conn = get_db()
    rows = conn.execute('''
        SELECT n.*, u.name AS user_name, u.email AS user_email
        FROM notifications n
        JOIN users u ON n.user_id = u.id
        ORDER BY n.created_at DESC
        LIMIT 200
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows]), 200


# === SLOT AVAILABILITY ===
@admin_api.route('/slots/availability', methods=['GET'])
def slots_availability():
    date = request.args.get('date', '')
    conn = get_db()
    rows = conn.execute('''
        SELECT s.id, s.slot_time, s.point_id, p.point_name, p.status AS point_status,
               st.id AS station_id, st.name AS station_name,
               b.id AS booking_id, b.status AS booking_status, u.name AS booked_by
        FROM slots s
        JOIN charging_points p ON s.point_id = p.id
        JOIN stations st ON p.station_id = st.id
        LEFT JOIN bookings b ON b.slot_id = s.id AND b.date = ?
        LEFT JOIN users u ON b.user_id = u.id
        ORDER BY st.id, p.id, s.id
    ''', (date,)).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        d['is_available'] = d['booking_status'] is None or d['booking_status'] == 'CANCELLED'
        result.append(d)
    return jsonify(result), 200
