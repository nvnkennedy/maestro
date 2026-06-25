# Database Migrations

Maestro 1.0 builds its SQLite schema automatically at startup
(`Base.metadata.create_all`). When a schema change ships after 1.0, add an
Alembic migration here:

```bash
alembic init backend/db/migrations
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
