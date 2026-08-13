from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default="volunteer")  # volunteer / coordinator / admin
    shelter_id = db.Column(db.Integer, db.ForeignKey("shelters.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    shelter = db.relationship("Shelter", foreign_keys=[shelter_id], backref="coordinator_user")
    offers = db.relationship("Offer", backref="volunteer", lazy=True)

    def is_admin(self):
        return self.role == "admin"

    def is_coordinator(self):
        return self.role == "coordinator"

    def is_volunteer(self):
        return self.role == "volunteer"


class Shelter(db.Model):
    __tablename__ = "shelters"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(300), nullable=False)
    neighborhood = db.Column(db.String(120))
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    capacity = db.Column(db.Integer, default=0)
    current_occupancy = db.Column(db.Integer, default=0)
    population_type = db.Column(db.String(50), default="mixed")  # families/elderly/children/migrants/mixed
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    offers = db.relationship("Offer", backref="shelter", lazy=True)

    def occupancy_pct(self):
        if self.capacity and self.capacity > 0:
            return round(self.current_occupancy / self.capacity * 100)
        return 0

    def population_label(self):
        labels = {
            "families": "Familias",
            "elderly": "Adultos mayores",
            "children": "Niños",
            "migrants": "Migrantes",
            "mixed": "Mixta",
        }
        return labels.get(self.population_type, self.population_type)

    def to_dict(self):
        from datetime import date
        today = date.today()
        aids_today = [
            o.title for o in self.offers
            if o.status == "accepted" and o.scheduled_date == today
        ]
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "neighborhood": self.neighborhood,
            "lat": self.lat,
            "lng": self.lng,
            "capacity": self.capacity,
            "current_occupancy": self.current_occupancy,
            "population_type": self.population_label(),
            "aid_today": ", ".join(aids_today) if aids_today else None,
        }


class Offer(db.Model):
    __tablename__ = "offers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    offer_type = db.Column(db.String(20), nullable=False)  # activity / food / goods
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    preferred_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="pending")  # pending / accepted / rejected
    shelter_id = db.Column(db.Integer, db.ForeignKey("shelters.id"), nullable=True)
    scheduled_date = db.Column(db.Date, nullable=True)
    admin_notes = db.Column(db.Text)
    contact_email = db.Column(db.String(200))
    contact_phone = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def type_label(self):
        labels = {"activity": "Actividad", "food": "Alimentos", "goods": "Artículos"}
        return labels.get(self.offer_type, self.offer_type)

    def type_icon(self):
        icons = {"activity": "ti-heart", "food": "ti-salad", "goods": "ti-package"}
        return icons.get(self.offer_type, "ti-gift")

    def status_badge(self):
        badges = {
            "pending": ("bg-warning-lt", "Pendiente"),
            "accepted": ("bg-success-lt", "Aceptada"),
            "rejected": ("bg-danger-lt", "Rechazada"),
        }
        return badges.get(self.status, ("bg-secondary-lt", self.status))


class MagicToken(db.Model):
    __tablename__ = "magic_tokens"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), nullable=False)
    token_hash = db.Column(db.String(200), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
