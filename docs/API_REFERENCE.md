# Maestro API Reference

Base URL: `http://localhost:8000/api` — interactive docs at `/api/docs`
(Swagger UI, generated from the OpenAPI schema at `/api/openapi.json`).

Authentication: requests act as the user named in the `X-Maestro-User`
header (default `admin`). RBAC applies once roles exist in the system.

## System

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness probe |
| GET | `/api/dashboard?project_id=` | Dashboard statistics |
| GET | `/metrics` | Prometheus metrics (no `/api` prefix) |
| WS | `/ws` | Live events: `execution_started`, `step_update`, `log`, `step_gate`, `execution_finished` |

## Projects

| Method | Path |
|---|---|
| GET / POST | `/api/projects` |
| GET / PUT / DELETE | `/api/projects/{id}` |
| GET | `/api/projects/{id}/stats` |

## Test cases

| Method | Path | Notes |
|---|---|---|
| GET | `/api/test-cases?project_id=` | List (no steps) |
| POST | `/api/test-cases` | Body includes `steps[]` |
| GET / PUT / DELETE | `/api/test-cases/{id}` | PUT replaces steps, snapshots a version |
| POST | `/api/test-cases/bulk-delete` | `{"ids": [..]}` |
| POST | `/api/test-cases/{id}/clone` | |
| GET | `/api/test-cases/templates` | Step template library |
| GET | `/api/test-cases/{id}/versions` | Version history |
| GET | `/api/test-cases/{id}/versions/diff?a=1&b=2` | Step-level diff |
| POST | `/api/test-cases/{id}/versions/{n}/rollback` | Restore version n |

### Test case body

```json
{
  "project_id": 1,
  "name": "Boot check",
  "test_type": "ssh",
  "scenario": "smoke",
  "steps": [
    {
      "step_number": 1,
      "action": "ssh.execute_command",
      "parameters": {"command": "uname -a", "device_config_id": 3},
      "timeout_seconds": 30,
      "retry_count": 1
    }
  ]
}
```

## Executions

| Method | Path | Notes |
|---|---|---|
| GET | `/api/executions?project_id=&test_case_id=&limit=` | History |
| POST | `/api/executions` | `{"test_case_id": 1, "mode": "serial"\|"parallel"\|"step"}` |
| GET | `/api/executions/{id}` | Includes step results |
| GET | `/api/executions/running` | Currently running ids |
| POST | `/api/executions/{id}/stop` \| `/pause` \| `/resume` \| `/next` | Control |
| DELETE | `/api/executions/{id}` | Not allowed while running |

## Reports

| Method | Path |
|---|---|
| GET | `/api/reports` |
| GET | `/api/reports/{execution_id}` (JSON summary) |
| GET | `/api/reports/{execution_id}/html` |
| GET | `/api/reports/{execution_id}/download` |
| POST | `/api/reports/compare` — `{"execution_a": 1, "execution_b": 2}` |
| POST | `/api/reports/bulk-delete` |

## Device configs

| Method | Path | Notes |
|---|---|---|
| GET | `/api/configs?project_id=&config_type=` | Credentials never returned |
| POST / PUT | `/api/configs[/{id}]` | `settings` plain, `credentials` encrypted at rest |
| DELETE | `/api/configs/{id}` · POST `/api/configs/bulk-delete` | |
| POST | `/api/configs/{id}/test` | Connectivity probe |

## Schedules

| Method | Path |
|---|---|
| GET / POST | `/api/schedules` |
| PUT / DELETE | `/api/schedules/{id}` |
| POST | `/api/schedules/{id}/toggle` |

### Schedule body (date-based)

```json
{ "test_case_id": 1, "schedule_type": "once",   "run_at": "2026-06-20T09:00:00" }
{ "test_case_id": 1, "schedule_type": "daily",  "time_of_day": "02:00" }
{ "test_case_id": 1, "schedule_type": "weekly", "time_of_day": "09:00", "weekday": 0 }
{ "test_case_id": 1, "schedule_type": "cron",   "cron_expression": "0 9 * * 1" }
```

`weekday`: 0 = Monday … 6 = Sunday. "once" schedules disable themselves
after firing. Responses include a human-readable `description`.

## Connections & plugins

| Method | Path |
|---|---|
| POST | `/api/connections/test` — `{"adapter": "ssh", "action": "execute_command", "params": {...}}` |
| GET | `/api/connections/health` — all adapter health checks |
| GET | `/api/connections/locks` — held device locks |
| GET | `/api/plugins` |
| POST | `/api/plugins/{name}/enable` \| `/disable` \| `/api/plugins/reload` |

## Datasets

| Method | Path |
|---|---|
| GET / POST | `/api/datasets` (`data_type`: `json` or `csv`, content in `raw`) |
| GET / PUT / DELETE | `/api/datasets/{id}` |

## Admin (RBAC & audit)

| Method | Path | Permission |
|---|---|---|
| GET / POST | `/api/admin/roles` | admin |
| DELETE | `/api/admin/roles/{id}` | admin |
| GET | `/api/admin/audit-logs?limit=` | audit |

Roles: `admin`, `designer`, `executor`, `viewer`, `auditor`.
