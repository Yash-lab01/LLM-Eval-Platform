# Current State

Last updated: 2026-09-23
Current phase: Phase 2 — Core Eval Engine (NEXT)

## Current Focus
Phase 1B (Data Layer + Schemas) complete. Ready to begin Phase 2 (LiteLLM client, parallel runner with asyncio.gather, Celery eval tasks, WebSocket handler, and POST /eval/run).

## Completed
- [x] All 5 docs written in /docs/
- [x] PROJECT_GUIDE.md updated with project-specific details and current model roster (Gemini 3.5+, Groq GPT-OSS/Qwen)
- [x] Phases reviewed and expanded to 10 phases
- [x] context/ folder created
- [x] Phase 0 complete: Project directories created, isolated `.venv` with Python 3.12, Poetry, Ruff, Pre-commit installed locally (zero global installs)
- [x] Phase 1A complete: `.env.example`, `docker-compose.yml` (8 services), `docker-compose.override.yml`, `gunicorn.conf.py`, `backend/core/config.py` (Pydantic-settings), `backend/main.py` (`GET /health`), pytest unit test passing
- [x] Phase 1B complete: All Pydantic v2 schemas in `backend/schemas/`, SQLAlchemy async engine + ORM models (5 tables with UUID keys and indexes), Alembic Migration 001, seed data script, and 12 unit tests passing cleanly

## In Progress
- Transitioning to Phase 2 (Core Eval Engine)

## Phase Status
| Phase | Status |
|---|---|
| Phase 0: Pre-Build Setup | Complete |
| Phase 1A: Infrastructure | Complete |
| Phase 1B: Data Layer + Schemas | Complete |
| Phase 2: Core Eval Engine | Next |
| Phase 3: Scoring + Feature Router | Not started |
| Phase 4: Observability + MCP | Not started |
| Phase 5: Frontend | Not started |
| Phase 6: Testing + Hardening | Not started |
| Phase 7A: Extra Features Core | Not started |
| Phase 7B: Extra Features Advanced | Not started |
| Phase 8: Portfolio Polish | Not started |

## Known Problems
None.

## Next Task
Phase 2: Implement LiteLLM wrapper (`services/litellm_client.py`), parallel runner (`services/eval_runner.py`), Celery eval task (`tasks/eval_tasks.py`), WebSocket handler (`/ws/eval/{run_id}`), and REST endpoints (`POST /api/v1/eval/run`).

## Do Not Change
- ModelID enum values (LiteLLM prefix format must match exactly)
- Redis DB allocation: DB 0 = cache, DB 1 = Celery broker, DB 2 = Celery results
- Feature Middleware location: always backend/middleware/feature_router.py
- All Pydantic schemas live only in backend/schemas/ — nowhere else
