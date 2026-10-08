from flask import Flask
from routes.views import views
from routes.api import api
from routes.auth import auth

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ev_charging_secret_key'

# Register blueprints
app.register_blueprint(views, url_prefix='/')
app.register_blueprint(api, url_prefix='/api')
app.register_blueprint(auth, url_prefix='/auth')

from routes.admin_api import admin_api
app.register_blueprint(admin_api, url_prefix='/api/admin')

if __name__ == '__main__':
    from database.db import init_db
    init_db()
    app.run(debug=True, port=5000)
