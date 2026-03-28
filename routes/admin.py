"""
Admin routes — password-protected user management.
Step 1: full CRUD for users so you can create accounts and get tokens for testing.
"""
import uuid
import os
import functools
from flask import Blueprint, jsonify, request, Response, render_template
from models import db, User

admin_bp = Blueprint('admin', __name__)


def require_admin(f):
    """HTTP Basic Auth using ADMIN_PASSWORD env var."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        admin_password = os.environ.get('ADMIN_PASSWORD', '')
        auth = request.authorization
        if not auth or auth.password != admin_password or auth.username != 'admin':
            return Response(
                'Unauthorized',
                401,
                {'WWW-Authenticate': 'Basic realm="Admin"'}
            )
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/', methods=['GET'])
@admin_bp.route('', methods=['GET'])
@require_admin
def admin_dashboard():
    """GET /admin — serve the admin web UI."""
    return render_template('admin.html')


@admin_bp.route('/users', methods=['GET'])
@require_admin
def list_users():
    """GET /admin/users — list all users."""
    users = User.query.order_by(User.created_at).all()
    return jsonify([u.to_dict() for u in users])


@admin_bp.route('/users', methods=['POST'])
@require_admin
def create_user():
    """
    POST /admin/users
    Body: { "name": "Mom", "phone_number": "+15555551234", "is_admin": false }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON body'}), 400

    name = data.get('name', '').strip()
    phone = data.get('phone_number', '').strip()
    is_admin = bool(data.get('is_admin', False))

    if not name:
        return jsonify({'error': 'name is required'}), 400
    if not phone:
        return jsonify({'error': 'phone_number is required'}), 400
    if not phone.startswith('+'):
        return jsonify({'error': 'phone_number must be in E.164 format (e.g. +15555551234)'}), 400

    user = User(name=name, phone_number=phone, is_admin=is_admin)
    db.session.add(user)
    db.session.commit()

    user_dict = user.to_dict()
    user_dict['url'] = f'/u/{user.access_token}'  # frontend URL hint
    return jsonify(user_dict), 201


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    """DELETE /admin/users/<id> — remove user and all associated data."""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'status': 'deleted', 'id': user_id})


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['PATCH'])
@require_admin
def toggle_active(user_id):
    """PATCH /admin/users/<id>/toggle-active — flip is_active."""
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'id': user_id, 'is_active': user.is_active})


@admin_bp.route('/users/<int:user_id>/regenerate-token', methods=['POST'])
@require_admin
def regenerate_token(user_id):
    """POST /admin/users/<id>/regenerate-token — issue a new access token."""
    user = User.query.get_or_404(user_id)
    user.access_token = str(uuid.uuid4())
    db.session.commit()
    return jsonify({
        'id': user_id,
        'access_token': user.access_token,
        'url': f'/u/{user.access_token}',
    })


@admin_bp.route('/users/<int:user_id>/test-sms', methods=['POST'])
@require_admin
def test_sms(user_id):
    """POST /admin/users/<id>/test-sms — send a real test SMS via Twilio."""
    from services.sms import send_sms, format_test_sms
    user = User.query.get_or_404(user_id)
    body = format_test_sms(user.name)
    success = send_sms(user.phone_number, body)
    if success:
        return jsonify({'status': 'sent', 'to': user.phone_number, 'body': body})
    return jsonify({'status': 'failed', 'to': user.phone_number,
                    'message': 'Twilio send failed — check server logs'}), 500


@admin_bp.route('/trigger-check', methods=['POST'])
@require_admin
def trigger_check():
    """POST /admin/trigger-check — run a weather check for all active users right now."""
    import threading
    from flask import current_app
    from services.weather import check_weather_for_user

    users = User.query.filter_by(is_active=True).all()
    if not users:
        return jsonify({'status': 'ok', 'message': 'No active users to check'})

    app = current_app._get_current_object()
    for user in users:
        thread = threading.Thread(
            target=check_weather_for_user,
            args=(app, user.id),
            daemon=True,
        )
        thread.start()

    return jsonify({
        'status': 'ok',
        'message': f'Weather check triggered for {len(users)} user(s). Watch server logs for results.',
        'users': [u.name for u in users],
    })
