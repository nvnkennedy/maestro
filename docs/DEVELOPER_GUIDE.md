# Maestro Developer Guide

How to extend, test and contribute to Maestro.

## Architecture at a glance

```
frontend/ (React 18 + TS + Vite + Tailwind)
   └── talks to /api (REST) and /ws (WebSocket)
backend/
   ├── api/        FastAPI routers (thin: validation + audit + service calls)
   ├── services/   Execution engine, reports, scheduling, plugins, locks
   ├── adapters/   Device integrations (plugin system)
   ├── models/     SQLAlchemy ORM (SQLite by default)
   ├── security/   AES-256 vault, RBAC, audit logging
   └── utils/      Logging, validators, helpers
```

Key runtime objects (singletons):
- `backend.services.test_executor.executor` — runs executions as asyncio tasks
- `backend.services.ws_manager.ws_manager` — broadcasts events to the UI
- `backend.adapters.adapter_registry.get_registry()` — plugin registry
- `backend.services.resource_lock_mgr.lock_manager` — per-device locks

## Writing a new adapter (plugin)

1. Create `backend/adapters/my_adapter/` with three files:

   **adapter.py**
   ```python
   from backend.adapters.base_adapter import AdapterResult, BaseAdapter

   class MyAdapter(BaseAdapter):
       name = "my_tool"
       description = "What it does"

       def _register_actions(self) -> None:
           self.actions = {"do_thing": self._do_thing}

       async def _do_thing(self, params: dict) -> AdapterResult:
           return AdapterResult(success=True, output="done")
   ```

   **manifest.json**
   ```json
   {
     "name": "my_tool",
     "version": "1.0.0",
     "type": "adapter",
     "capabilities": ["do_thing"],
     "dependencies": [],
     "entry_point": "adapter:MyAdapter"
   }
   ```

   **__init__.py** re-exporting the class.

2. Restart Maestro or call `POST /api/plugins/reload`. Steps can now use the
   action `my_tool.do_thing`.

Rules:
- Never raise from an action — return `AdapterResult(success=False, error=...)`.
  (`BaseAdapter.execute` catches exceptions and timeouts anyway.)
- Run blocking I/O in a thread (`loop.run_in_executor`) or subprocess
  (`self._run_subprocess`).
- If a step produces a file, set `data["artifact_path"]` and
  `data["artifact_type"]` — the executor records it as an execution artifact.
- Implement `health_check()`; it powers the dashboard's adapter health panel.

**Third-party plugins** follow the same layout but live in
`data/plugins/<name>/` and are loaded by `custom_script_loader.py`.

## Execution engine semantics

`TestExecutor._run_serial` walks steps by index and honours, in order:
1. `_if` conditional jumps (against earlier step outputs)
2. `_parallel_group` batching
3. step-by-step gating (`step` mode)
4. `_loop` iteration and retry-with-backoff inside `_execute_step`
5. failure → remaining steps marked `skipped` unless `_continue_on_failure`

Steps bound to a `device_config_id` acquire a per-device asyncio lock, so two
executions can't drive the same bench simultaneously.

## Database

Schema is created automatically (`Base.metadata.create_all`). For schema
changes post-1.0, add Alembic migrations under `backend/db/migrations/`.
Set `DATABASE_URL` to a PostgreSQL URL for larger installs.

## Security model

- Credentials: AES-256-GCM via `SecretsVault`; key derived from `SECRET_KEY`
  (PBKDF2) or auto-generated into `data/.vault.key`.
- RBAC: roles in the `user_roles` table; the acting user comes from the
  `X-Maestro-User` header. With no roles configured Maestro runs in open
  (single-user) mode.
- Every mutating endpoint writes an `audit_logs` row.

## Tests

```bash
python -m pytest tests/unit -v          # vault, validators, adapters, executor
python -m pytest tests/integration -v   # full API through TestClient
npm run test --prefix frontend          # vitest + testing-library
```

Note: FastAPI commits the request DB session *after* the response is sent, so
mutating endpoints call `db.commit()` explicitly before returning — keep doing
this in new endpoints to avoid read-after-write races.

## Code style

```bash
black backend/ tests/ && isort backend/ tests/ && flake8 backend/
npm run lint --prefix frontend
```

## Release flow

Tag `v*` → `release.yml` runs tests, builds `maestro-<version>.zip` and
publishes a GitHub release; `docker.yml` pushes the image to GHCR.
