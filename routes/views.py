from flask import Blueprint, render_template, session, redirect, url_for, abort

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
        return redirect(url_for('views.login'))
    if session.get('is_admin'):
        return redirect(url_for('views.admin_dashboard'))
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
        return redirect(url_for('views.login'))
    return render_template('book.html', slot_id=slot_id)

@views.route('/payment/<booking_id>')
def payment(booking_id):
    if 'user_id' not in session:
        return redirect(url_for('views.login'))
    return render_template('payment.html', booking_id=booking_id)

@views.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('views.login'))
    return render_template('history.html')

@views.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('views.login'))
    return render_template('notifications.html')

@views.route('/admin/login')
def admin_login():
    """Dedicated admin login page (visible to logged-out visitors)."""
    if session.get('is_admin'):
        return redirect(url_for('views.admin_dashboard'))
    return render_template('admin_login.html')

@views.route('/admin')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('views.admin_login'))
    if not session.get('is_admin'):
        abort(403)
    return render_template('admin_dashboard.html')
