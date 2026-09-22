# Current State

Last updated: 2026-09-22
Current phase: Phase 1B — Data Layer + Schemas (NEXT)

## Current Focus
Phase 0 (Pre-Build Setup) and Phase 1A (Infrastructure) complete. Ready to begin Phase 1B (SQLAlchemy models, Pydantic schemas, Alembic Migration 001).

## Completed
- [x] All 5 docs written in /docs/
- [x] PROJECT_GUIDE.md updated with project-specific details and current model roster (Gemini 3.5+, Groq GPT-OSS/Qwen)
- [x] Phases reviewed and expanded to 10 phases
- [x] context/ folder created
- [x] Phase 0 complete: Project directories created, isolated `.venv` with Python 3.12, Poetry, Ruff, Pre-commit installed locally (zero global installs)
- [x] Phase 1A complete: `.env.example`, `docker-compose.yml` (8 services), `docker-compose.override.yml`, `gunicorn.conf.py`, `backend/core/config.py` (Pydantic-settings), `backend/main.py` (`GET /health`), pytest unit test passing

## In Progress
- Transitioning to Phase 1B (Data Layer + Schemas)

## Phase Status
| Phase | Status |
|---|---|
| Phase 0: Pre-Build Setup | Complete |
| Phase 1A: Infrastructure | Complete |
| Phase 1B: Data Layer + Schemas | Next |
| Phase 2: Core Eval Engine | Not started |
| Phase 3: Scoring + Feature Router | Not started |
| Phase 4: Observability + MCP | Not started |
| Phase 5: Frontend | Not started |
| Phase 6: Testing + Hardening | Not started |
| Phase 7A: Extra Features Core | Not started |
| Phase 7B: Extra Features Advanced | Not started |
| Phase 8: Portfolio Polish | Not started |

## Known Problems
None. Docker daemon offline on host (expected until Docker Desktop is started for container execution).

## Next Task
Phase 1B: Implement SQLAlchemy async models, Pydantic v2 schemas (`backend/schemas/`), Alembic Migration 001, seed data script, and schema tests.

## Do Not Change
- ModelID enum values (LiteLLM prefix format must match exactly)
- Redis DB allocation: DB 0 = cache, DB 1 = Celery broker, DB 2 = Celery results
- Feature Middleware location: always backend/middleware/feature_router.py
- All Pydantic schemas live only in backend/schemas/ — nowhere else
