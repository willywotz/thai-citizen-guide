cd backend
uv pip install alembic==1.14.0
# OR
pip install alembic==1.14.0

# Generate initial migration from current models
alembic revision --autogenerate -m "initial"

# Apply migration
alembic upgrade head
What was set up:

alembic.ini — Alembic config (URL is overridden from settings.database_url)
alembic/env.py — async-compatible env; imports all models so autogenerate detects them
alembic/script.py.mako — migration file template
alembic/versions/ — where generated migrations live
The env.py pulls database_url directly from your app's settings, so you never need to duplicate the connection string.

Workflow going forward:


# After changing models.py:
alembic revision --autogenerate -m "describe your change"
alembic upgrade head