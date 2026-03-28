"""
National Weather Service API integration.
Docs: https://www.weather.gov/documentation/services-web-api
No API key required. Free for public use.
"""
import logging
import time
import requests

logger = logging.getLogger(__name__)

NWS_BASE    = 'https://api.weather.gov'
HEADERS     = {
    'User-Agent': 'WeatherAlertApp/1.0 (jzewski.online)',
    'Accept':     'application/geo+json',
}
TIMEOUT     = 10
RETRY_DELAY = 5  # seconds between retry attempts

# ── Filtering constants ───────────────────────────────────────────────────────

# Events always included regardless of severity field
PRIORITY_KEYWORDS = ['Tornado', 'Flash Flood', 'Severe Thunderstorm']

# Severity values that trigger an alert (NWS uses title-case)
HIGH_SEVERITY = {'Severe', 'Extreme'}

# Max alerts sent per polling cycle per user
MAX_ALERTS_PER_CYCLE = 2


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_alerts(lat: float, lon: float) -> list[dict] | None:
    """
    Fetch active NWS alerts for a geographic point.
    Retries once on failure.
    Returns a list (possibly empty) on success, or None if both attempts fail.
    Each returned dict has: id, event, severity, status, headline, description, area_desc.
    """
    url = f'{NWS_BASE}/alerts/active'
    params = {'point': f'{lat:.4f},{lon:.4f}'}

    for attempt in (1, 2):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            return _parse_alerts(resp.json())
        except Exception as exc:
            logger.warning('NWS fetch attempt %d failed: %s', attempt, exc)
            if attempt == 1:
                time.sleep(RETRY_DELAY)

    return None  # both attempts failed


def filter_and_sort(alerts: list[dict], sent_ids: set[str]) -> list[dict]:
    """
    Apply severity/event-type filter, skip already-sent alert IDs,
    sort by priority, and cap at MAX_ALERTS_PER_CYCLE.

    Priority order (ascending sort key):
      0 — Tornado
      1 — Flash Flood
      2 — Severe Thunderstorm
      3 — Other Severe/Extreme
    """
    passing = []
    for alert in alerts:
        if alert['status'] != 'Actual':
            continue
        if alert['id'] in sent_ids:
            continue
        if not _passes_filter(alert):
            continue
        passing.append(alert)

    passing.sort(key=_priority)
    return passing[:MAX_ALERTS_PER_CYCLE]


def fetch_for_display(lat: float, lon: float) -> list[dict]:
    """
    Live fetch for the status endpoint — no dedup, just filter for display.
    Returns all currently passing alerts (not capped).
    """
    alerts = fetch_alerts(lat, lon)
    return [a for a in alerts if a['status'] == 'Actual' and _passes_filter(a)]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_alerts(geojson: dict) -> list[dict]:
    results = []
    for feature in geojson.get('features', []):
        props = feature.get('properties', {})
        results.append({
            'id':          props.get('id', feature.get('id', '')),
            'event':       props.get('event', ''),
            'severity':    props.get('severity', ''),
            'status':      props.get('status', ''),
            'headline':    props.get('headline', ''),
            'description': props.get('description', ''),
            'area_desc':   props.get('areaDesc', ''),
        })
    return results


def _passes_filter(alert: dict) -> bool:
    event    = alert.get('event', '')
    severity = alert.get('severity', '')
    if severity in HIGH_SEVERITY:
        return True
    return any(kw.lower() in event.lower() for kw in PRIORITY_KEYWORDS)


def _priority(alert: dict) -> int:
    event = alert.get('event', '').lower()
    for i, kw in enumerate(PRIORITY_KEYWORDS):
        if kw.lower() in event:
            return i
    return len(PRIORITY_KEYWORDS)  # other Severe/Extreme
