"""
SMS sending via Twilio.
All message formatting lives here so the format is consistent and easy to adjust.
"""
import os
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

# Max chars for the headline portion of an alert SMS
_HEADLINE_MAX = 100


def _client() -> Client:
    return Client(
        os.environ['TWILIO_ACCOUNT_SID'],
        os.environ['TWILIO_AUTH_TOKEN'],
    )


def _from_number() -> str:
    return os.environ['TWILIO_FROM_NUMBER']


def send_sms(to_number: str, body: str) -> bool:
    """
    Send an SMS via Twilio. Returns True on success, False on failure.
    Logs errors but never raises — callers should check the return value.
    """
    try:
        msg = _client().messages.create(
            to=to_number,
            from_=_from_number(),
            body=body,
        )
        logger.info('SMS sent to %s — SID %s', to_number, msg.sid)
        return True
    except TwilioRestException as exc:
        logger.error('Twilio error sending to %s: %s', to_number, exc)
        return False
    except Exception as exc:
        logger.error('Unexpected error sending SMS to %s: %s', to_number, exc)
        return False


# ── Message formatters ────────────────────────────────────────────────────────

def format_alert_sms(alert: dict, city_state: str | None) -> str:
    """
    Weather alert SMS — target 160-320 chars (1-2 segments).

    Format:
        WEATHER ALERT: [Event Type]
        Near [City, State]
        [Headline up to 100 chars]
        Update location if you've moved.
    """
    location = city_state or 'your last known location'
    headline = alert.get('headline', '').strip()
    if len(headline) > _HEADLINE_MAX:
        headline = headline[:_HEADLINE_MAX].rstrip() + '…'

    parts = [
        f"WEATHER ALERT: {alert['event']}",
        f"Near {location}",
    ]
    if headline:
        parts.append(headline)
    parts.append('Update location if you have signal.')
    return '\n'.join(parts)


def format_stale_warning_sms(city_state: str | None, last_seen: str) -> str:
    """
    Stale location warning SMS.

    Format:
        Weather Alert: No location update in 12+ hrs.
        Last known: [City, State] ([time]).
        Open your link to update if you have signal.
    """
    location = city_state or 'unknown'
    return (
        f'Weather Alert: No location update in 12+ hrs.\n'
        f'Last known: {location} ({last_seen}).\n'
        f'Open your link to update if you have signal.'
    )


def format_test_sms(name: str) -> str:
    return f'Weather Alert System: Test message for {name}. System is working correctly.'


def format_failure_sms(user_name: str, error: str) -> str:
    err_short = str(error)[:80]
    return (
        f'Weather Alert System ERROR: NWS check failed for {user_name}.\n'
        f'Error: {err_short}\n'
        f'Check Render logs.'
    )
