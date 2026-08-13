# 🌊 Oshún

> Plataforma de coordinación de ayuda humanitaria para albergues en Cali, Colombia.

Oshún conecta a voluntarios y donantes con los albergues de Cali para que la ayuda llegue donde más se necesita — de forma equitativa, sin que ningún refugio se quede sin apoyo mientras otro se satura. Su nombre viene de la diosa yoruba/afrocolombiana de los ríos, símbolo de cuidado y generosidad, profundamente arraigada en la cultura de Cali.

---

## Tech Stack

- **Backend** — Python 3.12 · Flask 3.0 · SQLAlchemy 3.1 · Flask-Login 0.6 · Flask-Mail 0.10
- **Frontend** — Jinja2 · Tabler Bootstrap 5 (CDN) · Tabler Icons (CDN) · AOS 2.3.4 · Leaflet.js 1.9.4
- **Database** — SQLite (desarrollo) · PostgreSQL (producción)
- **Deployment** — Heroku (Procfile incluido)

---

## Features

| Feature | Descripción |
|---|---|
| **Magic-link auth** | Acceso sin contraseña — se envía un enlace al correo, válido por 1 hora |
| **Mapa interactivo** | Leaflet + OpenStreetMap, marcadores coloreados por nivel de ocupación |
| **Ofertas de ayuda** | Voluntarios registran actividades, alimentos o artículos (3 tipos) |
| **Dashboard admin** | Estadísticas, ofertas pendientes, asignación a albergues |
| **Dashboard coordinador** | Vista del propio albergue, ayudas próximas, actualización de ocupación |
| **Gestión de albergues** | Crear, editar, activar/desactivar, asignar coordinador |
| **Inventario de voluntarios** | Tabla de voluntarios con rol, historial de ayudas, cambio de rol |
| **Donaciones por albergue** | Vista consolidada de ofertas agrupadas por albergue |

---

## Architecture

```
Browser
  │
  ▼
app.py  (Flask routes — auth, volunteer, coordinator, admin)
  │
  ├── models.py  (User · Shelter · Offer · MagicToken — SQLAlchemy)
  │
  ├── config.py  (Config class — env vars con defaults)
  │
  └── templates/
        base.html           ← nav, flash alerts, CDN scripts
        index.html          ← hero, stats, mapa, directorio
        auth/               ← login, sent, magic_link_email
        volunteer/          ← dashboard, offer_form
        coordinator/        ← dashboard
        admin/              ← dashboard, offers, shelters, shelter_form,
                               volunteers, donations

static/
  css/custom.css   ← animaciones, AOS overrides, ocupación
  js/map.js        ← Leaflet init, marcadores, popups
```

---

## Getting Started

```bash
# 1. Clonar
git clone https://github.com/wilmer-erazo/oshun.git
cd oshun

# 2. Entorno virtual
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Variables de entorno
cp .env.example .env
# Editar .env con tus valores

# 4. Base de datos y datos iniciales
FLASK_DEBUG=1 flask seed

# 5. Correr
FLASK_DEBUG=1 flask run --port 5001
```

Abrir en `http://localhost:5001`. El admin inicial se crea con el email de `ADMIN_EMAIL`.

---

## Environment Variables

| Variable | Default | Descripción |
|---|---|---|
| `SECRET_KEY` | `dev-secret-change-me` | Clave de sesión Flask — **cambiar en prod** |
| `DATABASE_URL` | SQLite local | URL de PostgreSQL en Heroku |
| `MAIL_SERVER` | `smtp.gmail.com` | Servidor SMTP |
| `MAIL_PORT` | `587` | Puerto SMTP |
| `MAIL_USE_TLS` | `True` | Usar TLS |
| `MAIL_USERNAME` | *(vacío)* | Usuario SMTP — si está vacío, activa modo dev |
| `MAIL_PASSWORD` | *(vacío)* | Contraseña SMTP / app password |
| `MAIL_DEFAULT_SENDER` | *(vacío)* | Dirección remitente |
| `ADMIN_EMAIL` | `admin@alberguescali.com` | Email del admin inicial |
| `BASE_URL` | `http://localhost:5001` | URL base para magic links |

---

## Roles

| Rol | Acceso |
|---|---|
| `volunteer` | Registrar y ver sus propias ofertas de ayuda. Rol por defecto al crear cuenta. |
| `coordinator` | Todo lo anterior + dashboard de su albergue asignado + actualizar ocupación. |
| `admin` | Acceso completo: dashboard, ofertas, albergues, voluntarios, donaciones. |

Los roles se cambian desde **Admin → Voluntarios → botón Rol**.

---

## Deployment (Heroku)

```bash
heroku create nombre-de-tu-app
heroku addons:create heroku-postgresql:essential-0
heroku config:set SECRET_KEY="..." ADMIN_EMAIL="..." BASE_URL="https://nombre-de-tu-app.herokuapp.com"
heroku config:set MAIL_USERNAME="..." MAIL_PASSWORD="..." MAIL_DEFAULT_SENDER="..."
git push heroku main
heroku run flask seed
```

El `Procfile` ya está configurado: `web: gunicorn app:app`.

---

## GitHub

[github.com/wilmer-erazo/oshun](https://github.com/wilmer-erazo/oshun)
