import hashlib
import os
import secrets
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_mail import Mail, Message

from config import Config
from models import MagicToken, Offer, Shelter, User, db

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
mail = Mail(app)

login_manager = LoginManager(app)
login_manager.login_view = "auth_login"
login_manager.login_message = "Inicia sesión para continuar."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("Acceso restringido a administradores.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


def coordinator_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_coordinator():
            flash("Acceso restringido a coordinadores.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


# ─── Public ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    shelters = Shelter.query.filter_by(is_active=True).all()
    total_volunteers = User.query.filter_by(role="volunteer").count()
    aids_today = Offer.query.filter_by(status="accepted").filter(
        Offer.scheduled_date == date.today()
    ).count()
    return render_template(
        "index.html",
        shelters=shelters,
        total_volunteers=total_volunteers,
        aids_today=aids_today,
    )


@app.route("/api/shelters")
def api_shelters():
    shelters = Shelter.query.filter_by(is_active=True).all()
    return jsonify([s.to_dict() for s in shelters])


# ─── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/auth/login", methods=["GET", "POST"])
def auth_login():
    if current_user.is_authenticated:
        return redirect(_role_home())
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        if not email or not name:
            flash("Por favor completa todos los campos.", "warning")
            return redirect(url_for("auth_login"))

        user = User.query.filter_by(email=email).first()
        is_new_user = user is None
        if not user:
            user = User(name=name, email=email, role="volunteer")
            db.session.add(user)
            db.session.commit()
            base_url = app.config.get("BASE_URL", "http://localhost:5001")
            _send_whatsapp(
                f"🌊 *Nuevo voluntario registrado en Oshún*\n\n"
                f"👤 *Nombre:* {name}\n"
                f"📧 *Email:* {email}\n\n"
                f"🔗 Ver voluntarios: {base_url}/admin/volunteers"
            )

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(hours=1)

        MagicToken.query.filter_by(email=email, used=False).delete()
        magic = MagicToken(email=email, token_hash=token_hash, expires_at=expires_at)
        db.session.add(magic)
        db.session.commit()

        link = f"{app.config['BASE_URL']}/auth/verify/{token}"
        sent = _send_magic_link(user.name, email, link)

        if not sent:
            # Mail not configured — surface the link directly so dev/testing works
            from flask import session as flask_session
            flask_session["dev_link"] = link

        return redirect(url_for("auth_sent", email=email))
    return render_template("auth/login.html")


@app.route("/auth/sent")
def auth_sent():
    email = request.args.get("email", "")
    from flask import session as flask_session
    dev_link = flask_session.pop("dev_link", None)
    return render_template("auth/sent.html", email=email, dev_link=dev_link)


@app.route("/auth/verify/<token>")
def auth_verify(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    magic = MagicToken.query.filter_by(token_hash=token_hash, used=False).first()

    if not magic or magic.expires_at < datetime.utcnow():
        flash("El enlace ha expirado o no es válido. Solicita uno nuevo.", "danger")
        return redirect(url_for("auth_login"))

    user = User.query.filter_by(email=magic.email).first()
    if not user:
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for("auth_login"))

    magic.used = True
    db.session.commit()

    login_user(user, remember=True)

    from flask import session as flask_session
    pending = flask_session.pop("pending_offer", None)
    if pending:
        _save_offer(
            user,
            pending.get("offer_type", "goods"),
            pending.get("title", ""),
            pending.get("description", ""),
            pending.get("preferred_date"),
            pending.get("shelter_id"),
            pending.get("contact_email", ""),
            pending.get("contact_phone", ""),
        )
        flash(f"¡Bienvenido/a, {user.name}! Tu oferta fue registrada.", "success")
        return redirect(url_for("volunteer_dashboard"))

    flash(f"¡Bienvenido/a, {user.name}!", "success")
    return redirect(_role_home())


@app.route("/auth/logout")
@login_required
def auth_logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("index"))


def _role_home():
    if current_user.is_admin():
        return url_for("admin_dashboard")
    if current_user.is_coordinator():
        return url_for("coordinator_dashboard")
    return url_for("volunteer_dashboard")


def _send_magic_link(name, email, link):
    """Send magic link email. Returns True if sent, False if mail not configured."""
    if not app.config.get("MAIL_USERNAME"):
        print(f"\n[DEV] Magic link para {email}:\n{link}\n")
        return False
    try:
        msg = Message(
            subject="Tu enlace de acceso — Oshún",
            recipients=[email],
        )
        msg.body = (
            f"Hola {name},\n\n"
            f"Haz clic en el siguiente enlace para iniciar sesión:\n\n"
            f"{link}\n\n"
            f"Este enlace expira en 1 hora y solo puede usarse una vez.\n\n"
            f"— Equipo Oshún"
        )
        msg.html = render_template("auth/magic_link_email.html", name=name, link=link)
        mail.send(msg)
        return True
    except Exception as e:
        print(f"\n[ERROR] No se pudo enviar email a {email}: {e}\n{link}\n")
        return False


# ─── Volunteer ─────────────────────────────────────────────────────────────────

@app.route("/volunteer/dashboard")
@login_required
def volunteer_dashboard():
    offers = Offer.query.filter_by(user_id=current_user.id).order_by(Offer.created_at.desc()).all()
    return render_template("volunteer/dashboard.html", offers=offers)


@app.route("/volunteer/offer", methods=["GET", "POST"])
def volunteer_offer():
    from flask import session as flask_session
    shelters = Shelter.query.filter_by(is_active=True).all()
    today = date.today().isoformat()
    if request.method == "POST":
        offer_type = request.form.get("offer_type")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        preferred_date_str = request.form.get("preferred_date")
        shelter_id = request.form.get("shelter_id") or None
        contact_email = request.form.get("contact_email", "").strip()
        contact_phone = request.form.get("contact_phone", "").strip()

        if not offer_type or not title:
            flash("Por favor completa los campos obligatorios.", "warning")
            return render_template("volunteer/offer_form.html", shelters=shelters, today=today)

        if not current_user.is_authenticated:
            flask_session["pending_offer"] = {
                "offer_type": offer_type,
                "title": title,
                "description": description,
                "preferred_date": preferred_date_str,
                "shelter_id": shelter_id,
                "contact_email": contact_email,
                "contact_phone": contact_phone,
            }
            flash("¡Ya casi! Ingresa o crea tu cuenta para completar el envío.", "info")
            return redirect(url_for("auth_login"))

        _save_offer(current_user, offer_type, title, description,
                    preferred_date_str, shelter_id, contact_email, contact_phone)
        flash("¡Tu oferta fue enviada! El equipo la revisará pronto.", "success")
        return redirect(url_for("volunteer_dashboard"))

    return render_template("volunteer/offer_form.html", shelters=shelters, today=today)


def _save_offer(user, offer_type, title, description,
                preferred_date_str, shelter_id, contact_email, contact_phone):
    preferred_date = None
    if preferred_date_str:
        try:
            preferred_date = date.fromisoformat(preferred_date_str)
        except ValueError:
            pass
    offer = Offer(
        user_id=user.id,
        offer_type=offer_type,
        title=title,
        description=description,
        preferred_date=preferred_date,
        shelter_id=int(shelter_id) if shelter_id else None,
        contact_email=contact_email or None,
        contact_phone=contact_phone or None,
    )
    db.session.add(offer)
    db.session.commit()
    base_url = app.config.get("BASE_URL", "http://localhost:5001")
    type_labels = {"activity": "Actividad 🎨", "food": "Alimentos 🍱", "goods": "Artículos 📦"}
    wa_msg = (
        f"🌊 *Nueva ayuda registrada en Oshún*\n\n"
        f"👤 *Voluntario:* {user.name}\n"
        f"📋 *Tipo:* {type_labels.get(offer_type, offer_type)}\n"
        f"📝 *Descripción:* {title}\n"
    )
    if contact_email:
        wa_msg += f"📧 *Email:* {contact_email}\n"
    if contact_phone:
        wa_msg += f"📱 *Celular:* {contact_phone}\n"
    wa_msg += f"\n🔗 Ver dashboard: {base_url}/admin/dashboard"
    _send_whatsapp(wa_msg)


@app.route("/volunteer/offer/<int:offer_id>/cancel", methods=["POST"])
@login_required
def volunteer_cancel_offer(offer_id):
    offer = Offer.query.get_or_404(offer_id)
    if offer.user_id != current_user.id:
        flash("No tienes permiso para cancelar esta oferta.", "danger")
        return redirect(url_for("volunteer_dashboard"))
    if offer.status != "pending":
        flash("Solo puedes cancelar ofertas pendientes.", "warning")
        return redirect(url_for("volunteer_dashboard"))
    db.session.delete(offer)
    db.session.commit()
    flash("Oferta cancelada.", "info")
    return redirect(url_for("volunteer_dashboard"))


@app.route("/volunteer/offer/<int:offer_id>/edit", methods=["GET", "POST"])
@login_required
def volunteer_edit_offer(offer_id):
    offer = Offer.query.get_or_404(offer_id)
    if offer.user_id != current_user.id:
        flash("No tienes permiso para editar esta oferta.", "danger")
        return redirect(url_for("volunteer_dashboard"))
    if offer.status != "pending":
        flash("Solo puedes editar ofertas pendientes.", "warning")
        return redirect(url_for("volunteer_dashboard"))

    shelters = Shelter.query.filter_by(is_active=True).all()
    today = date.today().isoformat()

    if request.method == "POST":
        offer_type = request.form.get("offer_type")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        preferred_date_str = request.form.get("preferred_date")
        shelter_id = request.form.get("shelter_id") or None
        contact_email = request.form.get("contact_email", "").strip()
        contact_phone = request.form.get("contact_phone", "").strip()

        if not offer_type or not title:
            flash("Por favor completa los campos obligatorios.", "warning")
            return render_template("volunteer/offer_edit.html", offer=offer, shelters=shelters, today=today)

        preferred_date = None
        if preferred_date_str:
            try:
                preferred_date = date.fromisoformat(preferred_date_str)
            except ValueError:
                pass

        offer.offer_type = offer_type
        offer.title = title
        offer.description = description
        offer.preferred_date = preferred_date
        offer.shelter_id = int(shelter_id) if shelter_id else None
        offer.contact_email = contact_email or None
        offer.contact_phone = contact_phone or None
        db.session.commit()

        flash("¡Oferta actualizada exitosamente!", "success")
        return redirect(url_for("volunteer_dashboard"))

    return render_template("volunteer/offer_edit.html", offer=offer, shelters=shelters, today=today)


# ─── Coordinator ───────────────────────────────────────────────────────────────

@app.route("/coordinator/dashboard")
@login_required
@coordinator_required
def coordinator_dashboard():
    shelter = current_user.shelter
    upcoming = []
    if shelter:
        upcoming = (
            Offer.query.filter_by(shelter_id=shelter.id, status="accepted")
            .filter(Offer.scheduled_date >= date.today())
            .order_by(Offer.scheduled_date)
            .all()
        )
    return render_template("coordinator/dashboard.html", shelter=shelter, upcoming=upcoming)


@app.route("/coordinator/occupancy", methods=["POST"])
@login_required
@coordinator_required
def coordinator_occupancy():
    shelter = current_user.shelter
    if not shelter:
        flash("No tienes un albergue asignado.", "danger")
        return redirect(url_for("coordinator_dashboard"))
    try:
        new_occ = int(request.form.get("occupancy", 0))
        shelter.current_occupancy = max(0, min(new_occ, shelter.capacity))
        db.session.commit()
        flash("Ocupación actualizada.", "success")
    except (ValueError, TypeError):
        flash("Valor inválido.", "danger")
    return redirect(url_for("coordinator_dashboard"))


# ─── Admin ─────────────────────────────────────────────────────────────────────

@app.route("/admin/dashboard")
@login_required
@admin_required
def admin_dashboard():
    total_shelters = Shelter.query.filter_by(is_active=True).count()
    pending_offers = Offer.query.filter_by(status="pending").count()
    aids_today = Offer.query.filter_by(status="accepted").filter(
        Offer.scheduled_date == date.today()
    ).count()
    total_volunteers = User.query.filter_by(role="volunteer").count()
    pending = Offer.query.filter_by(status="pending").order_by(Offer.created_at.desc()).all()
    shelters = Shelter.query.filter_by(is_active=True).all()
    return render_template(
        "admin/dashboard.html",
        total_shelters=total_shelters,
        pending_offers=pending_offers,
        aids_today=aids_today,
        total_volunteers=total_volunteers,
        pending=pending,
        shelters=shelters,
    )


@app.route("/admin/offers")
@login_required
@admin_required
def admin_offers():
    status = request.args.get("status", "all")
    query = Offer.query.order_by(Offer.created_at.desc())
    if status != "all":
        query = query.filter_by(status=status)
    offers = query.all()
    shelters = Shelter.query.filter_by(is_active=True).all()
    return render_template("admin/offers.html", offers=offers, shelters=shelters, current_status=status)


@app.route("/admin/offers/<int:offer_id>/assign", methods=["POST"])
@login_required
@admin_required
def admin_assign_offer(offer_id):
    offer = Offer.query.get_or_404(offer_id)
    shelter_id = request.form.get("shelter_id")
    scheduled_date_str = request.form.get("scheduled_date")
    action = request.form.get("action", "accept")

    if action == "reject":
        offer.status = "rejected"
        offer.admin_notes = request.form.get("admin_notes", "")
        db.session.commit()
        flash("Oferta rechazada.", "warning")
        return redirect(url_for("admin_dashboard"))

    if not shelter_id or not scheduled_date_str:
        flash("Selecciona albergue y fecha.", "warning")
        return redirect(url_for("admin_dashboard"))

    try:
        scheduled_date = date.fromisoformat(scheduled_date_str)
    except ValueError:
        flash("Fecha inválida.", "danger")
        return redirect(url_for("admin_dashboard"))

    offer.status = "accepted"
    offer.shelter_id = int(shelter_id)
    offer.scheduled_date = scheduled_date
    offer.admin_notes = request.form.get("admin_notes", "")
    db.session.commit()

    _notify_offer_accepted(offer)
    flash("Oferta asignada exitosamente.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/shelters")
@login_required
@admin_required
def admin_shelters():
    shelters = Shelter.query.order_by(Shelter.name).all()
    coordinators = User.query.filter_by(role="coordinator").all()
    volunteers = User.query.filter_by(role="volunteer").all()
    return render_template(
        "admin/shelters.html",
        shelters=shelters,
        coordinators=coordinators,
        volunteers=volunteers,
    )


@app.route("/admin/shelters/new", methods=["GET", "POST"])
@login_required
@admin_required
def admin_shelter_new():
    if request.method == "POST":
        shelter = Shelter(
            name=request.form.get("name", "").strip(),
            address=request.form.get("address", "").strip(),
            neighborhood=request.form.get("neighborhood", "").strip(),
            lat=float(request.form.get("lat", 0)),
            lng=float(request.form.get("lng", 0)),
            capacity=int(request.form.get("capacity", 0)),
            current_occupancy=int(request.form.get("current_occupancy", 0)),
            population_type=request.form.get("population_type", "mixed"),
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(shelter)
        db.session.commit()
        flash("Albergue creado exitosamente.", "success")
        return redirect(url_for("admin_shelters"))
    return render_template("admin/shelter_form.html", shelter=None)


@app.route("/admin/shelters/<int:shelter_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def admin_shelter_edit(shelter_id):
    shelter = Shelter.query.get_or_404(shelter_id)
    if request.method == "POST":
        shelter.name = request.form.get("name", "").strip()
        shelter.address = request.form.get("address", "").strip()
        shelter.neighborhood = request.form.get("neighborhood", "").strip()
        shelter.lat = float(request.form.get("lat", shelter.lat))
        shelter.lng = float(request.form.get("lng", shelter.lng))
        shelter.capacity = int(request.form.get("capacity", shelter.capacity))
        shelter.current_occupancy = int(request.form.get("current_occupancy", shelter.current_occupancy))
        shelter.population_type = request.form.get("population_type", shelter.population_type)
        shelter.notes = request.form.get("notes", "").strip()
        shelter.is_active = "is_active" in request.form
        db.session.commit()
        flash("Albergue actualizado.", "success")
        return redirect(url_for("admin_shelters"))
    return render_template("admin/shelter_form.html", shelter=shelter)


@app.route("/admin/shelters/<int:shelter_id>/assign-coordinator", methods=["POST"])
@login_required
@admin_required
def admin_assign_coordinator(shelter_id):
    shelter = Shelter.query.get_or_404(shelter_id)
    user_id = request.form.get("user_id")
    if not user_id:
        flash("Selecciona un usuario.", "warning")
        return redirect(url_for("admin_shelters"))
    user = User.query.get_or_404(int(user_id))
    user.role = "coordinator"
    user.shelter_id = shelter.id
    db.session.commit()
    flash(f"{user.name} es ahora coordinador/a de {shelter.name}.", "success")
    return redirect(url_for("admin_shelters"))


@app.route("/admin/volunteers")
@login_required
@admin_required
def admin_volunteers():
    volunteers = User.query.filter(User.role.in_(["volunteer", "coordinator"])).order_by(User.name).all()
    return render_template("admin/volunteers.html", volunteers=volunteers)


@app.route("/admin/volunteers/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def admin_change_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get("role")
    if new_role in ("volunteer", "coordinator", "admin"):
        user.role = new_role
        if new_role != "coordinator":
            user.shelter_id = None
        db.session.commit()
        flash(f"Rol de {user.name} actualizado a {new_role}.", "success")
    return redirect(url_for("admin_volunteers"))


@app.route("/admin/donations")
@login_required
@admin_required
def admin_donations():
    shelters = Shelter.query.filter_by(is_active=True).order_by(Shelter.name).all()
    shelter_data = []
    for s in shelters:
        offers = Offer.query.filter_by(shelter_id=s.id).order_by(Offer.created_at.desc()).all()
        shelter_data.append({"shelter": s, "offers": offers})
    unassigned = Offer.query.filter(Offer.shelter_id.is_(None)).order_by(Offer.created_at.desc()).all()
    return render_template("admin/donations.html", shelter_data=shelter_data, unassigned=unassigned)


# WhatsApp setup (Meta Cloud API):
# 1. Create a Meta Business app at developers.facebook.com
# 2. Add "WhatsApp" product and get a test phone number
# 3. Generate a permanent token via a System User in Business Settings
# 4. Copy WHATSAPP_PHONE_ID from WhatsApp > Getting Started
# 5. Set WHATSAPP_NOTIFY_TO to comma-separated E.164 numbers (+573001234567,...)
# 6. Add recipient numbers in the Meta sandbox before going live
def _send_whatsapp(message: str):
    """Send WhatsApp message to all configured notify numbers via Meta Cloud API."""
    import requests as req
    token = app.config.get("WHATSAPP_TOKEN")
    phone_id = app.config.get("WHATSAPP_PHONE_ID")
    notify_to = app.config.get("WHATSAPP_NOTIFY_TO", "")
    if not token or not phone_id or not notify_to:
        return
    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for number in notify_to.split(","):
        number = number.strip()
        if not number:
            continue
        payload = {
            "messaging_product": "whatsapp",
            "to": number,
            "type": "text",
            "text": {"body": message},
        }
        try:
            req.post(url, json=payload, headers=headers, timeout=5)
        except Exception as e:
            print(f"[WhatsApp] Error sending to {number}: {e}")


def _notify_offer_accepted(offer):
    try:
        user = offer.volunteer
        shelter = offer.shelter
        msg = Message(
            subject="Tu oferta fue aceptada — Oshún",
            recipients=[user.email],
        )
        msg.body = (
            f"Hola {user.name},\n\n"
            f"Tu oferta '{offer.title}' fue aceptada.\n\n"
            f"Albergue: {shelter.name if shelter else 'Por confirmar'}\n"
            f"Fecha: {offer.scheduled_date.strftime('%d/%m/%Y') if offer.scheduled_date else 'Por confirmar'}\n"
            f"Dirección: {shelter.address if shelter else ''}\n\n"
            f"¡Gracias por tu ayuda!\n— Equipo Oshún"
        )
        mail.send(msg)
    except Exception:
        pass


# ─── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("errors/500.html"), 500


# ─── CLI seed ──────────────────────────────────────────────────────────────────

@app.cli.command("seed")
def seed():
    """Seed the database with initial data."""
    db.create_all()

    admin_email = app.config["ADMIN_EMAIL"]
    if not User.query.filter_by(email=admin_email).first():
        admin = User(name="Administrador", email=admin_email, role="admin")
        db.session.add(admin)
        print(f"Admin creado: {admin_email}")

    sample_shelters = [
        {
            "name": "Albergue Siloé",
            "address": "Cra 1 # 45-20, Siloé",
            "neighborhood": "Siloé",
            "lat": 3.4372,
            "lng": -76.5565,
            "capacity": 80,
            "current_occupancy": 62,
            "population_type": "families",
        },
        {
            "name": "Refugio Santa Elena",
            "address": "Cl 70 # 2B-15, Santa Elena",
            "neighborhood": "Santa Elena",
            "lat": 3.4680,
            "lng": -76.5280,
            "capacity": 50,
            "current_occupancy": 38,
            "population_type": "elderly",
        },
        {
            "name": "Centro de Acogida Marroquín",
            "address": "Cra 28 # 62-40, Marroquín",
            "neighborhood": "Marroquín",
            "lat": 3.4102,
            "lng": -76.5390,
            "capacity": 120,
            "current_occupancy": 89,
            "population_type": "migrants",
        },
        {
            "name": "Albergue Ciudad Jardín",
            "address": "Av. Roosevelt # 38-15, Ciudad Jardín",
            "neighborhood": "Ciudad Jardín",
            "lat": 3.3980,
            "lng": -76.5470,
            "capacity": 60,
            "current_occupancy": 21,
            "population_type": "children",
        },
        {
            "name": "Refugio El Poblado",
            "address": "Cl 5 # 23-10, El Poblado",
            "neighborhood": "El Poblado",
            "lat": 3.4550,
            "lng": -76.5150,
            "capacity": 90,
            "current_occupancy": 74,
            "population_type": "mixed",
        },
    ]

    for s in sample_shelters:
        if not Shelter.query.filter_by(name=s["name"]).first():
            shelter = Shelter(**s)
            db.session.add(shelter)
            print(f"Albergue creado: {s['name']}")

    db.session.commit()
    print("¡Seed completado!")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
