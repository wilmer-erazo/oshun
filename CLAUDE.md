# 🌊 Oshún — AI Context & Architecture Guide

This file is the mandatory entry point for any AI assistant working on this project.
Read it fully before touching any code.

---

## Project Overview

**Oshún** is a humanitarian aid coordination platform for temporary shelters (*albergues*) in Cali, Colombia. It solves a specific distribution problem: when disaster strikes, some shelters get flooded with donations while others get nothing. Oshún coordinates incoming volunteer offers and distributes them equitably across shelters based on need.

**Three types of users:**
- **Voluntarios** — register offers of help (activities, food, goods) via a 3-step form
- **Coordinadores** — manage a single assigned shelter, track occupancy, see upcoming aid
- **Administradores** — full access: assign offers to shelters, manage shelters, see all volunteers and donations

All UI text is in **Spanish**. Never add English-facing user text.

---

## Tech Stack (exact versions)

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | Flask 3.0.3 |
| ORM | Flask-SQLAlchemy 3.1.1 |
| Auth | Flask-Login 0.6.3 |
| Email | Flask-Mail 0.10.0 |
| Templates | Jinja2 (bundled with Flask) |
| UI framework | Tabler Bootstrap 5 `@1.0.0` via CDN |
| Icons | Tabler Icons webfont `@latest` via CDN — prefix `ti ti-*` |
| Animations | AOS 2.3.4 via cdnjs |
| Map | Leaflet.js 1.9.4 via unpkg |
| DB (dev) | SQLite — `instance/shelters.db` |
| DB (prod) | PostgreSQL via Heroku |
| WSGI (prod) | gunicorn 22.0.0 |

**CDN URLs (use these exactly, never guess versions):**
```html
<!-- Tabler CSS -->
https://cdn.jsdelivr.net/npm/@tabler/core@1.0.0/dist/css/tabler.min.css
<!-- Tabler Icons -->
https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css
<!-- Tabler JS -->
https://cdn.jsdelivr.net/npm/@tabler/core@1.0.0/dist/js/tabler.min.js
<!-- AOS CSS -->
https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.css
<!-- AOS JS -->
https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js
<!-- Leaflet CSS -->
https://unpkg.com/leaflet@1.9.4/dist/leaflet.css
<!-- Leaflet JS -->
https://unpkg.com/leaflet@1.9.4/dist/leaflet.js
```

---

## File Map

```
oshun/
├── app.py                  ← ALL Flask routes, auth logic, seed CLI, mail helpers
├── config.py               ← Config class — env var defaults, mail/db settings
├── models.py               ← SQLAlchemy models: User, Shelter, Offer, MagicToken
├── requirements.txt        ← pinned Python deps
├── Procfile                ← web: gunicorn app:app (Heroku)
├── runtime.txt             ← Python version for Heroku
├── .env.example            ← template for local .env
│
├── static/
│   ├── css/custom.css      ← all custom styles, AOS overrides, occupancy colors,
│   │                          page fade-in, card hover, hero gradient, badge pop
│   └── js/map.js           ← Leaflet map init (center: Cali 3.4516, -76.5320),
│                              shelter markers colored by occupancy, popup HTML
│
└── templates/
    ├── base.html           ← sticky nav with role-based tabs, flash alerts, footer,
    │                          all CDN <link>/<script> tags, AOS.init()
    ├── index.html          ← hero, 3 stat cards with quick-action buttons,
    │                          Leaflet map section, shelter directory cards, CTA
    ├── auth/
    │   ├── login.html      ← name + email form → POST /auth/login
    │   ├── sent.html       ← shows dev_link button in dev mode, email confirm otherwise
    │   └── magic_link_email.html ← HTML email template for magic links
    ├── volunteer/
    │   ├── dashboard.html  ← list of user's own offers with status badges
    │   └── offer_form.html ← 3-step form: type selector → details → contact info
    ├── coordinator/
    │   └── dashboard.html  ← shelter overview, upcoming aid, occupancy update form
    └── admin/
        ├── dashboard.html  ← stat cards, pending offers table, assign modal
        ├── offers.html     ← all offers with status filter tabs
        ├── shelters.html   ← shelter cards with edit + coordinator assign modal
        ├── shelter_form.html ← create/edit shelter form (name, address, lat/lng, etc.)
        ├── volunteers.html ← volunteer inventory table with role-change modal
        └── donations.html  ← offers grouped by shelter, plus unassigned section
```

---

## Models Reference

### User
```python
id, name, email (unique), role ('volunteer'|'coordinator'|'admin'),
shelter_id (FK → shelters, nullable), created_at

# Relationships
shelter       → Shelter (the shelter this coordinator manages)
offers        → [Offer]

# Methods
is_admin()        → bool
is_coordinator()  → bool
is_volunteer()    → bool
```

### Shelter
```python
id, name, address, neighborhood, lat, lng,
capacity, current_occupancy,
population_type ('families'|'elderly'|'children'|'migrants'|'mixed'),
notes, is_active, created_at

# Relationships
coordinator_user  → User (backref from User.shelter)
offers            → [Offer]

# Methods
occupancy_pct()     → int (0-100)
population_label()  → str (Spanish label)
to_dict()           → dict (for /api/shelters JSON endpoint)
```

### Offer
```python
id, user_id (FK → users), offer_type ('activity'|'food'|'goods'),
title, description, preferred_date (Date),
status ('pending'|'accepted'|'rejected'),
shelter_id (FK → shelters, nullable), scheduled_date (Date, nullable),
admin_notes, contact_email, contact_phone, created_at

# Relationships
volunteer  → User (backref)
shelter    → Shelter (backref)

# Methods
type_label()   → str ('Actividad'|'Alimentos'|'Artículos')
type_icon()    → str (Tabler icon class e.g. 'ti-heart')
status_badge() → tuple (css_class, label) e.g. ('bg-warning-lt', 'Pendiente')
```

### MagicToken
```python
id, email, token_hash (SHA-256 hex, unique), expires_at (DateTime), used (bool), created_at
```

---

## Routes Reference

### Public
| Route | Method | Description |
|---|---|---|
| `/` | GET | Home — hero, stats, map, shelter directory |
| `/api/shelters` | GET | JSON list of active shelters (for Leaflet map) |

### Auth
| Route | Method | Auth | Description |
|---|---|---|---|
| `/auth/login` | GET/POST | — | Login form; POST creates user if new, generates magic token, sends email |
| `/auth/sent` | GET | — | Confirmation page; shows dev_link if mail not configured |
| `/auth/verify/<token>` | GET | — | Validates token hash, logs user in, redirects to role home |
| `/auth/logout` | GET | ✓ | Clears session, redirects to index |

### Volunteer
| Route | Method | Auth | Description |
|---|---|---|---|
| `/volunteer/dashboard` | GET | ✓ | User's own offers list |
| `/volunteer/offer` | GET/POST | ✓ | 3-step offer form; POST saves Offer |

### Coordinator
| Route | Method | Auth | Role | Description |
|---|---|---|---|---|
| `/coordinator/dashboard` | GET | ✓ | coordinator | Shelter view + upcoming aid |
| `/coordinator/occupancy` | POST | ✓ | coordinator | Update current_occupancy |

### Admin
| Route | Method | Auth | Role | Description |
|---|---|---|---|---|
| `/admin/dashboard` | GET | ✓ | admin | Stats + pending offers + assign modal |
| `/admin/offers` | GET | ✓ | admin | All offers, filterable by status |
| `/admin/offers/<id>/assign` | POST | ✓ | admin | Accept (assign shelter+date) or reject offer |
| `/admin/shelters` | GET | ✓ | admin | All shelters with edit + coordinator modal |
| `/admin/shelters/new` | GET/POST | ✓ | admin | Create shelter |
| `/admin/shelters/<id>/edit` | GET/POST | ✓ | admin | Edit shelter |
| `/admin/shelters/<id>/assign-coordinator` | POST | ✓ | admin | Promote volunteer → coordinator |
| `/admin/volunteers` | GET | ✓ | admin | All volunteers + coordinators inventory |
| `/admin/volunteers/<id>/role` | POST | ✓ | admin | Change user role |
| `/admin/donations` | GET | ✓ | admin | Offers grouped by shelter |

---

## Role System

Roles are stored as strings on `User.role`. Two decorators in `app.py`:

```python
@admin_required     # redirects to index with danger flash if not admin
@coordinator_required  # redirects to index with danger flash if not coordinator
```

After magic-link login, `_role_home()` redirects:
- admin → `/admin/dashboard`
- coordinator → `/coordinator/dashboard`
- volunteer → `/volunteer/dashboard`

New users are always created as `volunteer`. Role changes are made by admin via `/admin/volunteers/<id>/role`.

---

## Auth Flow (Magic Link)

```
1. POST /auth/login  (name + email)
   ├── Create User if email not found (role='volunteer')
   ├── Generate: token = secrets.token_urlsafe(32)
   ├── Store:    token_hash = SHA-256(token) in magic_tokens table
   ├── Expire:   expires_at = now + 1 hour
   ├── Delete previous unused tokens for this email
   └── Send email (or store in session for dev mode)

2. GET /auth/sent
   └── If dev_link in session → show "Ingresar ahora" button
       Else → show "Revisa tu correo"

3. GET /auth/verify/<token>
   ├── Hash the token, look up in magic_tokens
   ├── Check: not used, not expired
   ├── Mark token as used
   ├── login_user(user, remember=True)
   └── Redirect to role home
```

---

## Dev Mode

**Trigger:** `MAIL_USERNAME` is `None` (not set in `.env`).

**Behavior:**
- `_send_magic_link()` prints the link to stdout and returns `False`
- `auth_login` stores the raw verify URL in `flask_session["dev_link"]`
- `auth_sent` pops it and passes to template as `dev_link`
- Template shows a prominent "🔧 Modo desarrollo / Ingresar ahora" button

No email config needed to test login locally.

---

## Database

- **Local:** SQLite at `instance/shelters.db` (auto-created, gitignored)
- **Production:** PostgreSQL via `DATABASE_URL` env var; `postgres://` prefix is rewritten to `postgresql://` in config.py for SQLAlchemy compatibility

**Schema management:** No Alembic. To add a column:
```python
# In Python after modifying the model:
import sqlite3
conn = sqlite3.connect('instance/shelters.db')
conn.execute('ALTER TABLE offers ADD COLUMN new_col VARCHAR(200)')
conn.commit()
```

**Seed command:**
```bash
flask seed
```
Creates: 1 admin user (`ADMIN_EMAIL`) + 5 Cali shelters. Safe to re-run — uses `filter_by().first()` before inserting.

---

## Template Conventions

All templates extend `base.html`. Standard page structure:

```html
{% extends "base.html" %}
{% block title %}Page Title — Oshún{% endblock %}

{% block content %}
<!-- Page header band -->
<div class="page-top">
  <div class="container">
    <h2 class="section-title" data-aos="fade-right">
      <i class="ti ti-icon-name text-primary me-2"></i>Título
    </h2>
  </div>
</div>

<!-- Page content -->
<div class="container pb-5">
  <div class="card" data-aos="fade-up">
    ...
  </div>
</div>
{% endblock %}
```

**Nav tabs** in `base.html` are role-gated via `{% if current_user.is_admin() %}` etc. Active tab uses `{% if request.endpoint == 'route_name' %}active{% endif %}`.

---

## AOS Animation Rules

AOS (`data-aos="fade-up"`) hides elements with `opacity: 0` until scroll triggers the animation.

**Use AOS on:** cards that are above the fold or reachable naturally by scrolling.

**Do NOT use AOS on:** elements near the bottom of long pages that a user must scroll to — they may never animate in automated/screenshot contexts and will appear invisible.

**If an element gets stuck transparent:** remove its `data-aos` attribute. This has already happened with the contact form card in `offer_form.html` (step 3).

---

## Critical Gotchas

1. **Template caching in non-debug mode.** Flask without `FLASK_DEBUG=1` caches Jinja2 compiled templates in memory. Template edits won't be seen until the server restarts. Always develop with `FLASK_DEBUG=1`.

2. **AOS opacity:0 trap.** See AOS section above. Has already caused invisible form sections.

3. **BASE_URL must match Flask port.** Default is `http://localhost:5001`. If you run on a different port, the magic link verify URL will be wrong. Either set `BASE_URL` in `.env` or keep port 5001.

4. **Two GitHub accounts.** The repo `wilmer-erazo/oshun` belongs to the personal account. Pushes must use that account's token:
   ```bash
   TOKEN=$(gh auth token --hostname github.com --user wilmer-erazo)
   git remote set-url origin "https://wilmer-erazo:${TOKEN}@github.com/wilmer-erazo/oshun.git"
   git push origin main
   git remote set-url origin "https://github.com/wilmer-erazo/oshun.git"  # clean up token
   ```

5. **`coordinator_user` is a list backref.** `Shelter.coordinator_user` is a backref from `User.shelter` using `foreign_keys=[shelter_id]`. In templates it may return a list — check existing templates for correct usage before referencing it.

---

## Good Practices (Project-Specific)

- **Run locally:** `FLASK_DEBUG=1 .venv/bin/flask run --port 5001`
- **All UI text in Spanish** — no English user-facing strings, ever
- **After model changes:** manually `ALTER TABLE` the SQLite DB, then restart server
- **Icons:** always `<i class="ti ti-icon-name"></i>` — icon list at tabler.io/icons
- **New admin pages:** add route in `app.py` with `@admin_required`, add template in `templates/admin/`, add nav tab in `base.html` inside the `{% if current_user.is_admin() %}` block
- **Occupancy colors:** use CSS classes `occ-low` (<50%), `occ-medium` (50–80%), `occ-high` (>80%) defined in `custom.css`
- **Status badges:** use `offer.status_badge()` which returns `(css_class, label)` tuple — render as `<span class="badge {{ badge[0] }}">{{ badge[1] }}</span>`
- **Never commit:** `instance/`, `.env`, `__pycache__/`, `.venv/` — all in `.gitignore`

---

## Running the Project

```bash
cd /Users/wreyes/Documents/personals/shelters
FLASK_DEBUG=1 .venv/bin/flask run --port 5001
```

Admin login: use `flask seed` email (`admin@alberguescali.com` by default) at `/auth/login`.
In dev mode the magic link appears directly on the `/auth/sent` page.

**GitHub:** https://github.com/wilmer-erazo/oshun
