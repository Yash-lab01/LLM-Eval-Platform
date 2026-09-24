# Current State

Last updated: 2026-09-24
Current phase: Phase 4 — Observability + MCP (NEXT)

## Current Focus
Phase 3 (Scoring + Feature Router + Leaderboard) complete with 36/36 tests passing. Ready to begin Phase 4 (Langfuse observability integration, trace wrapping, FastMCP server with eval tools, and MCP docker compose integration).

## Completed
- [x] All 5 docs written in /docs/
- [x] PROJECT_GUIDE.md updated with project-specific details and current model roster (Gemini 3.5+, Groq GPT-OSS/Qwen)
- [x] Phases reviewed and expanded to 10 phases
- [x] context/ folder created
- [x] Phase 0 complete: Project directories created, isolated `.venv` with Python 3.12, Poetry, Ruff, Pre-commit installed locally (zero global installs)
- [x] Phase 1A complete: `.env.example`, `docker-compose.yml` (8 services), `docker-compose.override.yml`, `gunicorn.conf.py`, `backend/core/config.py` (Pydantic-settings), `backend/main.py` (`GET /health`), pytest unit test passing
- [x] Phase 1B complete: All Pydantic v2 schemas in `backend/schemas/`, SQLAlchemy async engine + ORM models (5 tables with UUID keys and indexes), Alembic Migration 001, seed data script, and 12 unit tests passing cleanly
- [x] Phase 2 complete: LiteLLM streaming wrapper with backoff retry, parallel runner with asyncio.gather, Redis pub/sub token broadcasting, memory-safe WebSocket endpoint (`/ws/eval/{run_id}`), Celery worker task (`eval_default`), REST API (`POST /api/v1/eval/run`, `GET /api/v1/eval/{run_id}`, history list), API key auth dependency, and 19 unit/integration tests passing cleanly
- [x] Phase 3 complete: FeatureRouter middleware gating metrics based on consumer config, non-blocking PyTorch BERTScore execution via `run_in_executor`, ROUGE-L similarity, latency/cost evaluation, ORM persistence, dynamic winner determination, Leaderboard SQL aggregation with win rate calculation, Redis caching (TTL 300s), `GET /api/v1/leaderboard`, and `GET /api/v1/models/recommend` endpoints. 36 unit/integration tests passing cleanly.

## In Progress
- Transitioning to Phase 4 (Observability + MCP)

## Phase Status
| Phase | Status |
|---|---|
| Phase 0: Pre-Build Setup | Complete |
| Phase 1A: Infrastructure | Complete |
| Phase 1B: Data Layer + Schemas | Complete |
| Phase 2: Core Eval Engine | Complete |
| Phase 3: Scoring + Feature Router | Complete |
| Phase 4: Observability + MCP | Next |
| Phase 5: Frontend | Not started |
| Phase 6: Testing + Hardening | Not started |
| Phase 7A: Extra Features Core | Not started |
| Phase 7B: Extra Features Advanced | Not started |
| Phase 8: Portfolio Polish | Not started |

## Known Problems
None.

## Next Task
Phase 4: Observability + MCP — Integrate Langfuse tracing into LiteLLM calls and scoring, wrap evaluation pipeline in traces, implement FastMCP server (`mcp/`) exposing tools (`run_eval`, `get_leaderboard`, `recommend_model`), and configure MCP container.

## Do Not Change
- ModelID enum values (LiteLLM prefix format must match exactly)
- Redis DB allocation: DB 0 = cache, DB 1 = Celery broker, DB 2 = Celery results
- Feature Middleware location: always backend/middleware/feature_router.py
- All Pydantic schemas live only in backend/schemas/ — nowhere else
