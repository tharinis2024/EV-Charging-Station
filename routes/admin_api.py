from flask import Blueprint, request, jsonify, session
from database.db import get_db

admin_api = Blueprint('admin_api', __name__)

def is_admin():
    return session.get('is_admin') == 1 or session.get('is_admin') is True

@admin_api.before_request
def check_admin():
    if not is_admin():
        return jsonify({'error': 'Forbidden: Admin access required'}), 403

# === STATIONS ===
@admin_api.route('/stations', methods=['GET'])
def get_stations():
    conn = get_db()
    stations = conn.execute('SELECT * FROM stations').fetchall()
    conn.close()
    return jsonify([dict(s) for s in stations]), 200

@admin_api.route('/stations', methods=['POST'])
def add_station():
    data = request.json
    conn = get_db()
    conn.execute('''
        INSERT INTO stations (name, location, operating_hours, connector_types, price_per_kwh, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (data['name'], data['location'], data['operating_hours'], data['connector_types'], data['price_per_kwh'], data.get('status', 'ACTIVE')))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Station added successfully'}), 201

@admin_api.route('/stations/<int:id>', methods=['PUT'])
def edit_station(id):
    data = request.json
    conn = get_db()
    conn.execute('''
        UPDATE stations SET name=?, location=?, operating_hours=?, connector_types=?, price_per_kwh=?, status=?
        WHERE id=?
    ''', (data['name'], data['location'], data['operating_hours'], data['connector_types'], data['price_per_kwh'], data['status'], id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Station updated successfully'}), 200

@admin_api.route('/stations/<int:id>', methods=['DELETE'])
def delete_station(id):
    conn = get_db()
    conn.execute('DELETE FROM stations WHERE id=?', (id,))
    # Cascade deletes theoretically needed, but for simplicity relying on DB or keeping orphans if not strictly enforced
    conn.commit()
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
    data = request.json
    conn = get_db()
    conn.execute('INSERT INTO charging_points (station_id, point_name, status) VALUES (?, ?, ?)',
                 (data['station_id'], data['point_name'], data.get('status', 'ACTIVE')))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Charging point added'}), 201

@admin_api.route('/points/<int:id>', methods=['PUT'])
def edit_point(id):
    data = request.json
    conn = get_db()
    if 'status' in data:
        conn.execute('UPDATE charging_points SET station_id=?, point_name=?, status=? WHERE id=?',
                     (data['station_id'], data['point_name'], data['status'], id))
    else:
        # Backwards compatible with the original payload (no status field)
        conn.execute('UPDATE charging_points SET station_id=?, point_name=? WHERE id=?',
                     (data['station_id'], data['point_name'], id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Charging point updated'}), 200

@admin_api.route('/points/<int:id>', methods=['DELETE'])
def delete_point(id):
    conn = get_db()
    conn.execute('DELETE FROM charging_points WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Charging point deleted'}), 200

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
    data = request.json
    conn = get_db()
    conn.execute('INSERT INTO slots (point_id, slot_time) VALUES (?, ?)',
                 (data['point_id'], data['slot_time']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Slot added'}), 201

@admin_api.route('/slots/<int:id>', methods=['PUT'])
def edit_slot(id):
    data = request.json
    conn = get_db()
    conn.execute('UPDATE slots SET point_id=?, slot_time=? WHERE id=?',
                 (data['point_id'], data['slot_time'], id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Slot updated'}), 200

@admin_api.route('/slots/<int:id>', methods=['DELETE'])
def delete_slot(id):
    conn = get_db()
    conn.execute('DELETE FROM slots WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Slot deleted'}), 200

# === BOOKINGS ===
@admin_api.route('/bookings', methods=['GET'])
def get_bookings():
    conn = get_db()
    bookings = conn.execute('''
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
        ORDER BY b.date DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(b) for b in bookings]), 200


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
        'active_bookings': count("SELECT COUNT(*) FROM bookings WHERE status IN ('PENDING','CONFIRMED','CHARGING')"),
        'completed_sessions': count("SELECT COUNT(*) FROM bookings WHERE status = 'COMPLETED'"),
        'cancelled_bookings': count("SELECT COUNT(*) FROM bookings WHERE status = 'CANCELLED'"),
        'revenue': count("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'SUCCESS'")
    }
    conn.close()
    return jsonify(stats), 200


# === USER MANAGEMENT (passwords are never selected) ===
@admin_api.route('/users', methods=['GET'])
def get_users():
    conn = get_db()
    users = conn.execute('''
        SELECT u.id, u.name, u.email, u.phone, u.is_admin,
               COUNT(b.id) AS booking_count,
               COALESCE(SUM(CASE WHEN b.status = 'CANCELLED' THEN 1 ELSE 0 END), 0) AS cancelled_count
        FROM users u
        LEFT JOIN bookings b ON b.user_id = u.id
        GROUP BY u.id
        ORDER BY u.id
    ''').fetchall()
    conn.close()
    return jsonify([dict(u) for u in users]), 200


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
