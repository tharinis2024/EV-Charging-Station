import uuid
from flask import session, jsonify

def generate_booking_id():
    return 'BKG' + str(uuid.uuid4().hex[:8]).upper()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function
