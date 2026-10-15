import os

from flask import Flask, jsonify, render_template
from routes.views import views
from routes.api import api
from routes.auth import auth

# Static assets live in public/static so Vercel serves them straight from its
# CDN (https://vercel.com/docs/frameworks/backend/flask#serving-static-assets)
# while Flask serves the exact same /static/* URLs locally.
# url_for('static', ...) keeps working unchanged everywhere.
app = Flask(__name__, static_folder='public/static', static_url_path='/static')

# Secret must come from the environment in production (set SECRET_KEY in
# Vercel); the fallback exists only so local development keeps working.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ev_charging_secret_key')

if os.environ.get('VERCEL') and not os.environ.get('SECRET_KEY'):
    print('[WARN] SECRET_KEY environment variable is not set; sessions are '
          'using the insecure development fallback. Set SECRET_KEY in Vercel.')

if os.environ.get('VERCEL'):
    # Vercel serves the app over HTTPS only.
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Register blueprints
app.register_blueprint(views, url_prefix='/')
app.register_blueprint(api, url_prefix='/api')
app.register_blueprint(auth, url_prefix='/auth')

from routes.admin_api import admin_api
app.register_blueprint(admin_api, url_prefix='/api/admin')

# ─── Error Handlers ───────────────────────────────────────────────────────────
@app.errorhandler(403)
def forbidden(e):
    """Return JSON for API calls, HTML redirect for browser requests."""
    from flask import request
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Forbidden: Admin access required'}), 403
    # HTML page: show a friendly message
    return (
        "<html><body style='font-family:sans-serif;text-align:center;padding:4rem;background:#0a0f1e;color:#e9effc'>"
        "<h1 style='color:#ef4444'>403 — Access Denied</h1>"
        "<p>You do not have permission to view this page.</p>"
        "<a href='/' style='color:#00e58f'>Return Home</a>"
        "</body></html>"
    ), 403

@app.errorhandler(404)
def not_found(e):
    from flask import request
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return (
        "<html><body style='font-family:sans-serif;text-align:center;padding:4rem;background:#0a0f1e;color:#e9effc'>"
        "<h1 style='color:#f59e0b'>404 — Page Not Found</h1>"
        "<p>The page you are looking for does not exist.</p>"
        "<a href='/' style='color:#00e58f'>Return Home</a>"
        "</body></html>"
    ), 404

@app.errorhandler(500)
def server_error(e):
    from flask import request
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return (
        "<html><body style='font-family:sans-serif;text-align:center;padding:4rem;background:#0a0f1e;color:#e9effc'>"
        "<h1 style='color:#ef4444'>500 — Server Error</h1>"
        "<p>Something went wrong. Please try again later.</p>"
        "<a href='/' style='color:#00e58f'>Return Home</a>"
        "</body></html>"
    ), 500

if __name__ == '__main__':
    from database.db import init_db
    init_db()
    app.run(debug=True, port=5000)
