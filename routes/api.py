from flask import Blueprint, request, jsonify, session
from database.db import get_db
from utils.helpers import generate_booking_id

api = Blueprint('api', __name__)

@api.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')

    if not all([name, email, phone, password]):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db()
    try:
        conn.execute('INSERT INTO users (name, email, phone, password) VALUES (?, ?, ?, ?)',
                     (name, email, phone, password))
        conn.commit()
        return jsonify({'message': 'Registration successful'}), 201
    except Exception as e:
        return jsonify({'error': 'Email already exists'}), 400
    finally:
        conn.close()

@api.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
    conn.close()

    if user:
        session['user_id'] = user['id']
        session['name'] = user['name']
        session['is_admin'] = user['is_admin']
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'is_admin': bool(user['is_admin'])
            }
        }), 200
    return jsonify({'error': 'Invalid credentials'}), 401

@api.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200

@api.route('/stations', methods=['GET'])
def get_stations():
    search = request.args.get('search', '')
    conn = get_db()
    if search:
        stations = conn.execute('SELECT * FROM stations WHERE name LIKE ? OR location LIKE ?', 
                                (f'%{search}%', f'%{search}%')).fetchall()
    else:
        stations = conn.execute('SELECT * FROM stations').fetchall()
    conn.close()
    return jsonify([dict(s) for s in stations]), 200

@api.route('/stations/<int:id>', methods=['GET'])
def get_station(id):
    conn = get_db()
    station = conn.execute('SELECT * FROM stations WHERE id = ?', (id,)).fetchone()
    if not station:
        conn.close()
        return jsonify({'error': 'Station not found'}), 404
        
    points = conn.execute('SELECT * FROM charging_points WHERE station_id = ?', (id,)).fetchall()
    conn.close()
    
    st_dict = dict(station)
    st_dict['points'] = [dict(p) for p in points]
    return jsonify(st_dict), 200

@api.route('/stations/<int:id>/slots', methods=['GET'])
def get_station_slots(id):
    date = request.args.get('date') # Not strictly used in schema yet, but good for real logic
    conn = get_db()
    query = '''
        SELECT s.id, s.slot_time, p.point_name, p.id as point_id,
        (SELECT status FROM bookings WHERE slot_id = s.id AND date = ? AND status != 'CANCELLED') as booking_status
        FROM slots s
        JOIN charging_points p ON s.point_id = p.id
        WHERE p.station_id = ?
    '''
    slots = conn.execute(query, (date, id)).fetchall()
    conn.close()
    
    result = []
    for s in slots:
        d = dict(s)
        d['is_available'] = d['booking_status'] is None
        result.append(d)
        
    return jsonify(result), 200

@api.route('/bookings', methods=['POST'])
def create_booking():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    slot_id = data.get('slot_id')
    date = data.get('date')
    
    conn = get_db()
    
    # Check if already booked
    existing = conn.execute('SELECT * FROM bookings WHERE slot_id = ? AND date = ? AND status != "CANCELLED"', 
                           (slot_id, date)).fetchone()
    if existing:
        conn.close()
        return jsonify({'error': 'Slot already booked'}), 400
        
    # Get slot details for amount
    slot = conn.execute('''
        SELECT st.price_per_kwh FROM slots s
        JOIN charging_points p ON s.point_id = p.id
        JOIN stations st ON p.station_id = st.id
        WHERE s.id = ?
    ''', (slot_id,)).fetchone()
    
    if not slot:
        conn.close()
        return jsonify({'error': 'Slot not found'}), 404
        
    amount = slot['price_per_kwh'] * 50 # Fixed amount simulation
    booking_id = generate_booking_id()
    
    conn.execute('''
        INSERT INTO bookings (id, user_id, slot_id, date, amount, status)
        VALUES (?, ?, ?, ?, ?, "PENDING")
    ''', (booking_id, session['user_id'], slot_id, date, amount))
    
    conn.execute('INSERT INTO notifications (user_id, message) VALUES (?, ?)',
                 (session['user_id'], f'Booking {booking_id} created successfully.'))
                 
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Booking created', 'booking_id': booking_id, 'amount': amount}), 201

@api.route('/bookings/<id>', methods=['GET'])
def get_booking(id):
    conn = get_db()
    booking = conn.execute('''
        SELECT b.*, s.slot_time, p.point_name, st.name as station_name, st.location 
        FROM bookings b
        JOIN slots s ON b.slot_id = s.id
        JOIN charging_points p ON s.point_id = p.id
        JOIN stations st ON p.station_id = st.id
        WHERE b.id = ?
    ''', (id,)).fetchone()
    conn.close()
    
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
        
    return jsonify(dict(booking)), 200

@api.route('/bookings/<id>/cancel', methods=['PUT'])
def cancel_booking(id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    conn = get_db()
    booking = conn.execute('SELECT * FROM bookings WHERE id = ? AND user_id = ?', 
                          (id, session['user_id'])).fetchone()
                          
    if not booking:
        conn.close()
        return jsonify({'error': 'Booking not found'}), 404
        
    conn.execute('UPDATE bookings SET status = "CANCELLED" WHERE id = ?', (id,))
    conn.execute('UPDATE charging_sessions SET status = "CANCELLED" WHERE booking_id = ?', (id,))
    
    conn.execute('INSERT INTO notifications (user_id, message) VALUES (?, ?)',
                 (session['user_id'], f'Booking {id} has been cancelled.'))
                 
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Booking cancelled successfully'}), 200

@api.route('/payments', methods=['POST'])
def process_payment():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    booking_id = data.get('booking_id')
    method = data.get('method')
    
    conn = get_db()
    booking = conn.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,)).fetchone()
    
    if not booking:
        conn.close()
        return jsonify({'error': 'Booking not found'}), 404
        
    # Simulate payment failure
    status = 'FAILED' if method == 'FAIL' else 'SUCCESS'
    
    conn.execute('''
        INSERT INTO payments (booking_id, amount, method, status)
        VALUES (?, ?, ?, ?)
    ''', (booking_id, booking['amount'], method, status))
    
    if status == 'SUCCESS':
        conn.execute('UPDATE bookings SET status = "CONFIRMED" WHERE id = ?', (booking_id,))
        conn.execute('INSERT INTO charging_sessions (booking_id) VALUES (?)', (booking_id,))
        conn.execute('INSERT INTO notifications (user_id, message) VALUES (?, ?)',
                 (session['user_id'], f'Payment for booking {booking_id} was successful.'))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Payment processed', 'status': status}), 201
    else:
        conn.execute('INSERT INTO notifications (user_id, message) VALUES (?, ?)',
                 (session['user_id'], f'Payment for booking {booking_id} failed.'))
        conn.commit()
        conn.close()
        return jsonify({'error': 'Payment failed', 'status': status}), 400

@api.route('/charging/start', methods=['POST'])
def start_charging():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    booking_id = data.get('booking_id')
    
    conn = get_db()
    conn.execute("UPDATE charging_sessions SET status = 'CHARGING', start_time = CURRENT_TIMESTAMP WHERE booking_id = ?", (booking_id,))
    conn.execute("UPDATE bookings SET status = 'CHARGING' WHERE id = ?", (booking_id,))
    conn.execute("INSERT INTO notifications (user_id, message) VALUES (?, ?)", 
                 (session['user_id'], f'Charging session for booking {booking_id} started.'))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Charging started'}), 200

@api.route('/charging/complete', methods=['POST'])
def complete_charging():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    booking_id = data.get('booking_id')
    
    conn = get_db()
    conn.execute("UPDATE charging_sessions SET status = 'COMPLETED', end_time = CURRENT_TIMESTAMP, duration = 60, energy_consumed = 50.0 WHERE booking_id = ?", (booking_id,))
    conn.execute("UPDATE bookings SET status = 'COMPLETED' WHERE id = ?", (booking_id,))
    
    conn.execute('INSERT INTO notifications (user_id, message) VALUES (?, ?)',
                 (session['user_id'], f'Charging session for booking {booking_id} completed.'))
                 
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Charging completed'}), 200

@api.route('/users/<int:id>/bookings', methods=['GET'])
def get_user_bookings(id):
    if 'user_id' not in session or (session['user_id'] != id and not session.get('is_admin')):
        return jsonify({'error': 'Unauthorized'}), 401
        
    conn = get_db()
    bookings = conn.execute('''
        SELECT b.*, s.slot_time, p.point_name, st.name as station_name, cs.duration, cs.energy_consumed, cs.start_time, cs.end_time 
        FROM bookings b
        JOIN slots s ON b.slot_id = s.id
        JOIN charging_points p ON s.point_id = p.id
        JOIN stations st ON p.station_id = st.id
        LEFT JOIN charging_sessions cs ON b.id = cs.booking_id
        WHERE b.user_id = ?
        ORDER BY b.date DESC
    ''', (id,)).fetchall()
    conn.close()
    
    return jsonify([dict(b) for b in bookings]), 200

@api.route('/notifications', methods=['GET'])
def get_notifications():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    conn = get_db()
    notifications = conn.execute(
        'SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC', 
        (session['user_id'],)
    ).fetchall()
    
    # Optional: mark as read
    conn.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0', (session['user_id'],))
    conn.commit()
    conn.close()
    
    return jsonify([dict(n) for n in notifications]), 200
