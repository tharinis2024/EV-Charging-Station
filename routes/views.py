from flask import Blueprint, render_template, session

views = Blueprint('views', __name__)

@views.route('/')
def index():
    return render_template('index.html')

@views.route('/login')
def login():
    return render_template('login.html')

@views.route('/register')
def register():
    return render_template('register.html')

@views.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return render_template('login.html')
    if session.get('is_admin'):
        return render_template('admin_dashboard.html')
    return render_template('dashboard.html')

@views.route('/stations')
def stations():
    return render_template('stations.html')

@views.route('/stations/<int:id>')
def station_details(id):
    return render_template('station_details.html', station_id=id)

@views.route('/book/<int:slot_id>')
def book(slot_id):
    if 'user_id' not in session:
        return render_template('login.html')
    return render_template('book.html', slot_id=slot_id)

@views.route('/payment/<booking_id>')
def payment(booking_id):
    if 'user_id' not in session:
        return render_template('login.html')
    return render_template('payment.html', booking_id=booking_id)

@views.route('/history')
def history():
    if 'user_id' not in session:
        return render_template('login.html')
    return render_template('history.html')

@views.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return render_template('login.html')
    return render_template('notifications.html')

@views.route('/admin')
def admin_dashboard():
    if not session.get('is_admin'):
        return render_template('index.html')
    return render_template('admin_dashboard.html')
