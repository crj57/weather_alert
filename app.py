import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from models import db


def create_app():
    app = Flask(__name__)

    # Render sets DATABASE_URL with the legacy postgres:// scheme; SQLAlchemy needs postgresql://
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///weather_alert.db')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', '')

    frontend_url = os.environ.get('FRONTEND_URL', '*')
    CORS(app, origins=frontend_url)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # ------------------------------------------------------------------ #
    #  Health check — use this to confirm the server + DB are up          #
    #  curl http://localhost:5000/health                                   #
    # ------------------------------------------------------------------ #
    @app.route('/health')
    def health():
        try:
            db.session.execute(db.text('SELECT 1'))
            db_status = 'ok'
        except Exception as e:
            db_status = f'error: {e}'
        return jsonify({
            'status': 'ok',
            'db': db_status,
            'database_url': database_url.split('@')[-1] if '@' in database_url else database_url,
        })

    # Register route blueprints
    from routes.api import api_bp
    from routes.admin import admin_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
