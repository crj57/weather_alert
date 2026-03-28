"""
Weather check logic — queries NWS, handles stale warnings, sends SMS alerts.
"""
import logging
from datetime import datetime, timedelta

from services.nws import fetch_alerts, filter_and_sort, fetch_for_display
from services.sms import (
    send_sms,
    format_alert_sms,
    format_stale_warning_sms,
    format_failure_sms,
)

logger = logging.getLogger(__name__)

STALE_HOURS = 12


def check_weather_for_user(app, user_id: int):
    """
    Full weather check for one user.
    Called immediately after a location POST and by the cron poller every 10 min.
    """
    with app.app_context():
        from models import db, User, SentAlert

        user = User.query.get(user_id)
        if not user or not user.is_active:
            return

        loc = user.latest_location
        if not loc:
            logger.info('[%s] No location on file — skipping', user.name)
            return

        logger.info('[%s] Checking weather at (%.4f, %.4f) — %s',
                    user.name, loc.lat, loc.lon, loc.city_state or 'unknown')

        # ── Stale location warning ────────────────────────────────────────────
        age = datetime.utcnow() - loc.timestamp
        if age > timedelta(hours=STALE_HOURS) and not user.stale_warning_sent:
            last_seen = loc.timestamp.strftime('%b %-d at %-I:%M %p UTC')
            body = format_stale_warning_sms(loc.city_state, last_seen)
            logger.info('[%s] Location stale (%dh) — sending warning', user.name,
                        int(age.total_seconds() // 3600))
            if send_sms(user.phone_number, body):
                user.stale_warning_sent = True
                db.session.commit()

        # ── Fetch NWS alerts ──────────────────────────────────────────────────
        sent_ids = {
            sa.alert_id
            for sa in SentAlert.query.filter_by(user_id=user.id).all()
        }

        raw_alerts = fetch_alerts(loc.lat, loc.lon)

        if raw_alerts is None:
            logger.error('[%s] NWS fetch failed after retry — notifying admins', user.name)
            _notify_admins(User, user.name, 'NWS API unavailable after retry')
            return

        if not raw_alerts:
            logger.info('[%s] No active NWS alerts at this location', user.name)
            return

        alerts = filter_and_sort(raw_alerts, sent_ids)

        if not alerts:
            logger.info('[%s] No new qualifying alerts', user.name)
            return

        # ── Send SMS for each qualifying alert ────────────────────────────────
        for alert in alerts:
            body = format_alert_sms(alert, loc.city_state)
            logger.info('[%s] Sending: %s (%s)', user.name, alert['event'], alert['severity'])
            logger.debug('SMS body:\n%s', body)

            if send_sms(user.phone_number, body):
                db.session.add(SentAlert(alert_id=alert['id'], user_id=user.id))
                user.last_alert_sent_at = datetime.utcnow()
                db.session.commit()
            else:
                logger.error('[%s] SMS failed for alert %s', user.name, alert['id'])


def _notify_admins(User, failed_user_name: str, error: str):
    """Send a failure SMS to all active admin users."""
    admins = User.query.filter_by(is_admin=True, is_active=True).all()
    body = format_failure_sms(failed_user_name, error)
    for admin in admins:
        send_sms(admin.phone_number, body)


def get_active_alerts_for_display(lat: float, lon: float) -> list[dict]:
    """Live filtered alerts for the GET /api/status endpoint. No dedup."""
    return fetch_for_display(lat, lon)
