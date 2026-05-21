"""
API routes — user-facing endpoints.
"""
import threading
from flask import Blueprint, jsonify, request, current_app
from models import db, User, Location
from services.geocode import reverse_geocode
from services.weather import check_weather_for_user, get_active_alerts_for_display

api_bp = Blueprint('api', __name__)


@api_bp.route('/location', methods=['POST'])
def post_location():
    """
    POST /api/location
    Body: { "token": "<uuid>", "lat": 39.7, "lon": -104.9 }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON body'}), 400

    token = data.get('token')
    lat = data.get('lat')
    lon = data.get('lon')

    if not token:
        return jsonify({'error': 'Missing token'}), 400
    if lat is None or lon is None:
        return jsonify({'error': 'Missing lat or lon'}), 400
    if not isinstance(lat, (int, float)) or not (-90 <= lat <= 90):
        return jsonify({'error': 'lat must be a float between -90 and 90'}), 400
    if not isinstance(lon, (int, float)) or not (-180 <= lon <= 180):
        return jsonify({'error': 'lon must be a float between -180 and 180'}), 400

    user = User.query.filter_by(access_token=token).first()
    if not user:
        return jsonify({'error': 'Invalid token'}), 401
    if not user.is_active:
        return jsonify({'error': 'Account is inactive'}), 403

    city_state = reverse_geocode(lat, lon)

    location = Location(user_id=user.id, lat=lat, lon=lon, city_state=city_state)
    user.stale_warning_sent = False
    db.session.add(location)
    db.session.commit()

    # Trigger an immediate weather check in a background thread so the
    # response returns right away without blocking on NWS + Twilio calls.
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=check_weather_for_user,
        args=(app, user.id),
        daemon=True,
    )
    thread.start()

    return jsonify({
        'status': 'ok',
        'message': f'Location received for {user.name}',
        'city_state': city_state,
    })


@api_bp.route('/enroll', methods=['POST'])
def enroll():
    """
    POST /api/enroll
    Public self-enrollment with SMS consent.
    Creates an inactive user (pending admin approval).
    Body: { "name": "Mom", "phone_number": "+15555551234", "consent_given": true }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON body'}), 400

    name    = (data.get('name') or '').strip()
    phone   = (data.get('phone_number') or '').strip()
    consent = data.get('consent_given', False)

    if not name:
        return jsonify({'error': 'name is required'}), 400
    if not phone:
        return jsonify({'error': 'phone_number is required'}), 400
    if not phone.startswith('+'):
        return jsonify({'error': 'phone_number must be in E.164 format (e.g. +15555551234)'}), 400
    if not consent:
        return jsonify({'error': 'consent_given must be true'}), 400

    existing = User.query.filter_by(phone_number=phone).first()
    if existing:
        return jsonify({'error': 'A request for this phone number already exists'}), 409

    user = User(name=name, phone_number=phone, is_active=False)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        'status': 'pending',
        'message': f'Enrollment request received for {name}. The administrator will activate your account.',
    }), 201


@api_bp.route('/status/<token>', methods=['GET'])
def get_status(token):
    """
    GET /api/status/<token>
    Returns user name, last location, and active alerts.
    """
    user = User.query.filter_by(access_token=token).first()
    if not user:
        return jsonify({'error': 'Invalid token'}), 401

    loc = user.latest_location

    alerts = []
    if loc:
        raw = get_active_alerts_for_display(loc.lat, loc.lon)
        alerts = [
            {'event': a['event'], 'severity': a['severity'], 'headline': a['headline']}
            for a in raw
        ]

    return jsonify({
        'name': user.name,
        'is_active': user.is_active,
        'last_location': loc.to_dict() if loc else None,
        'active_alerts': alerts,
    })
