#!/usr/bin/env python3
"""
Weather alert poller — runs as a Render Cron Job every 10 minutes.
Schedule: */10 * * * *

Can also be run manually:
    python3 poller.py
"""
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run():
    from app import create_app
    from services.weather import check_weather_for_user

    app = create_app()

    with app.app_context():
        from models import User
        users = User.query.filter_by(is_active=True).all()

    if not users:
        logger.info('Poller: no active users — exiting')
        return

    logger.info('Poller: checking %d active user(s)', len(users))

    for user in users:
        logger.info('--- %s ---', user.name)
        try:
            check_weather_for_user(app, user.id)
        except Exception as exc:
            logger.exception('Unhandled error checking user %s: %s', user.name, exc)

    logger.info('Poller: done')


if __name__ == '__main__':
    run()
