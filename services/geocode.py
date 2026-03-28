"""
Reverse geocoding via OSM Nominatim (free, no API key required).
Returns a human-readable "City, ST" string for a lat/lon pair.
"""
import requests

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse'
HEADERS = {'User-Agent': 'WeatherAlertApp/1.0 (jzewski.online)'}
TIMEOUT = 5


def reverse_geocode(lat: float, lon: float) -> str | None:
    """
    Returns a string like "Denver, CO" or None on failure.
    Falls back through city → town → village → county for the locality name.
    """
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={'lat': lat, 'lon': lon, 'format': 'json'},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        addr = data.get('address', {})

        locality = (
            addr.get('city')
            or addr.get('town')
            or addr.get('village')
            or addr.get('county')
            or addr.get('state_district')
        )
        state = addr.get('state')

        if locality and state:
            # Abbreviate state name to 2-letter code using the display_name if available
            state_abbr = _state_abbr(state)
            return f'{locality}, {state_abbr}'
        if locality:
            return locality
        return None
    except Exception:
        return None


# fmt: off
_STATE_MAP = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
    'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
    'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
    'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
    'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
    'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
    'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
    'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
    'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC',
}
# fmt: on


def _state_abbr(state: str) -> str:
    return _STATE_MAP.get(state, state)
