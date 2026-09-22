# Coding Conventions

## Python

- Python 3.12+. Use `X | Y` union syntax, not `Optional[X]`.
- Dedicated local virtual environment: always use isolated `.venv/` at project root (`py -3.12 -m venv .venv`). Never install dependencies or tools globally.
- All async functions prefixed with nothing — just `async def`. Do not use `async_` prefix.
- All files use `ruff` formatting. Run `pre-commit` before every commit.
- Imports: stdlib → third-party → local (ruff enforces this).

## Pydantic v2

- `model_dump()` not `dict()`. `model_validate()` not `parse_obj()`.
- `model_config = ConfigDict(from_attributes=True)` for ORM models.
- Cross-field validation uses `@model_validator(mode="after")`.
- All optional fields: `field: str | None = None` (not `Optional[str]`).

## SQLAlchemy

- Always `async with AsyncSession(engine) as session:`.
- Always `await session.commit()` after writes.
- All ORM models in `backend/models/` — never mix with Pydantic schemas.
- UUID primary keys only. Never integer IDs.

## FastAPI

- All route handlers are `async def`.
- DB sessions injected via `Depends(get_db)`.
- No business logic in route handlers — call services instead.
- All endpoints versioned: `/api/v1/...`.

## Celery

- Tasks go to named queues: `eval_default` or `eval_batch`.
- All tasks use `bind=True` for retry access.
- Never use `time.sleep()` — use `await asyncio.sleep()` in async, or Celery retry with backoff.

## Redis

- Always namespace keys: `cache:`, `auth:`, `run:` prefixes.
- Always set TTL on cache keys.
- Always `await pubsub.unsubscribe()` in WebSocket finally block.

## LiteLLM

- Always use exact model string with prefix: `gemini/gemini-3.5-flash` not `gemini-3.5-flash`.
- Always pass `metadata=` dict with `run_id`, `consumer_id`, `task_type`.
- Always `await litellm.acompletion()` — never sync `litellm.completion()` in async code.

## MCP

- MCP tools must have clear docstrings — they become tool descriptions in Cursor.
- Return Pydantic models from MCP tools — FastMCP serializes automatically.
- In stdio mode: all logs go to `stderr`. Never `print()` to stdout.

## Testing

- `asyncio_mode = "auto"` in pyproject.toml — no `@pytest.mark.asyncio` needed per test.
- Mock LiteLLM with `pytest-mock` or `unittest.mock`. Never real API calls in tests.
- Test file names: `test_{module_name}.py`. Test function names: `test_{what}_{condition}`.

## Git — Commit Convention

### Rule: One concern per commit. Never mix layers in one commit.

Each commit must touch **one layer only**. If you changed the backend AND the frontend, that is **two separate commits**.

### Commit Message Format

```
<type>(<scope>): <short description>
```

- **type** — what kind of change
- **scope** — which layer/area was changed
- **description** — what specifically happened (lowercase, no period at end)

### Types

| Type | When to use |
|---|---|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `refactor` | Code change with no behavior change |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `chore` | Tooling, config, dependencies |
| `perf` | Performance improvement |
| `style` | Formatting, linting (no logic change) |

### Scopes (use exactly these — one per commit)

| Scope | What it covers |
|---|---|
| `backend` | FastAPI routes, services, models (general) |
| `schemas` | Pydantic v2 schema changes only |
| `db` | SQLAlchemy models, Alembic migrations |
| `celery` | Celery tasks, queue config |
| `scoring` | PyTorch scorers, feature router |
| `litellm` | LiteLLM client, model config |
| `ws` | WebSocket handler |
| `mcp` | FastMCP server, MCP tools |
| `frontend` | Next.js pages, components, stores |
| `infra` | Docker, docker-compose, gunicorn, Redis config |
| `tests` | Test files only |
| `docs` | Markdown docs in /docs/ or /context/ |
| `ci` | GitHub Actions, pre-commit, ruff config |

### Examples

```bash
feat(backend): add POST /api/v1/eval/run endpoint
feat(schemas): add EvalConsumerConfig and FeatureFlag enum
feat(db): add alembic migration 001 with 5 core tables
feat(celery): add run_eval_task with exponential backoff retry
feat(scoring): add BERTScore F1 scorer with run_in_executor
feat(litellm): add LiteLLM client wrapper with Langfuse callback
feat(ws): add WebSocket eval streaming with Redis pub/sub
feat(mcp): add run_eval and get_best_model MCP tools
feat(frontend): add eval runner page with live token streaming
feat(infra): add docker-compose with 8 services
fix(ws): add try/finally pubsub cleanup on WebSocket disconnect
fix(celery): fix queue routing for eval_batch tasks
test(scoring): add unit tests for BERTScore with deterministic input
test(backend): add integration test for POST /eval/run with mocked LiteLLM
docs(context): update CURRENT_STATE.md after Phase 2 completion
chore(infra): add docker-compose.override.yml for local dev hot reload
refactor(backend): extract scoring logic from eval_runner into scoring.py
```

### What must NEVER be in one commit

```
❌ feat(backend): add eval endpoint and update leaderboard page
   → Split: feat(backend) + feat(frontend)

❌ feat(schemas): add schemas and update DB migration
   → Split: feat(schemas) + feat(db)

❌ fix(ws): fix websocket and update tests and update docs
   → Split: fix(ws) + test(ws) + docs(context)
```

### Branch naming

```
feature/phase-1a-infrastructure
feature/phase-2-eval-engine
feature/phase-3-scoring-feature-router
fix/websocket-redis-cleanup
fix/celery-queue-routing
docs/update-architecture
test/add-feature-router-coverage
```

- Never commit `.env` — it is in `.gitignore`, verify before every push.
- Never commit `__pycache__/`, `.pyc`, `.DS_Store`.
- Run `pre-commit` before every commit (ruff formatting + lint).

## Frontend (Next.js)

- App Router only. No Pages Router.
- All API types from `frontend/types/api.ts` — generated, never hand-edit.
- Zustand stores in `frontend/stores/`.
- shadcn/ui components only — no raw HTML buttons/inputs.
- `dark` mode class on `<html>` — dark mode is the default.
