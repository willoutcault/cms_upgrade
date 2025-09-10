# Campaign Tracker (Flask MVP)

A lightweight Flask app to track Brands, Campaigns, Programs, and Placements—
with simple CRUD, search, and relational linking.

## Quickstart

1) Create and fill in your `.env` (copy from `.env.sample`). By default it uses SQLite (no setup needed).
2) Create a virtualenv and install requirements:

```bash
python -m venv .venv
source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
```

3) Run the app:

```bash
python run.py
```

4) Visit http://127.0.0.1:5000

## Switching to Postgres or MySQL

Update `DATABASE_URL` in `.env` (examples below) and restart:

- Postgres: `postgresql+psycopg2://user:pass@host:5432/dbname`
- MySQL:    `mysql+pymysql://user:pass@host:3306/dbname`

On first run, the app will create tables if they don't exist.

## Entities

- **Brand** → has many Campaigns
- **Campaign** → belongs to Brand; has many Programs
- **Program** → belongs to Campaign; has many Placements
- **Placement** → belongs to Program (channel/email/app/dx/cmd), optional veeva_code & ad_server_id

All rows include `created_at` / `updated_at` timestamps.

## Seed sample data (optional)

```bash
python seed.py
```

This inserts a demo brand, campaign, program, and placement to try the UI.

## Notes

- This is intentionally minimal: pure Flask + SQLAlchemy + Jinja + Bootstrap.
- Add authentication, role-based access, audit logs, and Flask-Migrate/Alembic in a follow-up.
- API endpoints (`/api/...`) return JSON for easy integration with dashboards/other services.
