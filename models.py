import uuid
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    access_token = db.Column(db.String(36), unique=True, nullable=False,
                             default=lambda: str(uuid.uuid4()))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    last_alert_sent_at = db.Column(db.DateTime, nullable=True)
    # True after stale warning sent; reset to False on each new location update
    stale_warning_sent = db.Column(db.Boolean, default=False, nullable=False)

    locations = db.relationship('Location', backref='user', lazy=True,
                                cascade='all, delete-orphan',
                                order_by='Location.timestamp.desc()')
    sent_alerts = db.relationship('SentAlert', backref='user', lazy=True,
                                  cascade='all, delete-orphan')

    @property
    def latest_location(self):
        return self.locations[0] if self.locations else None

    def to_dict(self):
        loc = self.latest_location
        return {
            'id': self.id,
            'name': self.name,
            'phone_number': self.phone_number,
            'access_token': self.access_token,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_alert_sent_at': self.last_alert_sent_at.isoformat() if self.last_alert_sent_at else None,
            'last_location': loc.to_dict() if loc else None,
        }


class Location(db.Model):
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    city_state = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'lat': self.lat,
            'lon': self.lon,
            'city_state': self.city_state,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }


class SentAlert(db.Model):
    __tablename__ = 'sent_alerts'

    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sent_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint('alert_id', 'user_id', name='uq_alert_user'),
    )
