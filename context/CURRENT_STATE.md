# Current State

Last updated: 2026-09-25
Current phase: Phase 6 — Testing + Hardening (NEXT)

## Current Focus
Phase 5 (Frontend) complete with Next.js 15, TypeScript, Tailwind CSS, Zustand, and real-time WebSocket streaming. Ready to begin Phase 6 (End-to-End Testing, Chaos/Failure Hardening, and Load Testing).

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
- [x] Phase 4 complete: Langfuse telemetry callback integration in LiteLLM, standardized session and trace metadata injection, `compare_eval_runs` service and `GET /api/v1/eval/compare` REST endpoint, FastMCP server (`mcp.eval_server`) exposing 5 tools (`health_check`, `run_eval`, `get_best_model`, `get_eval_history`, `compare_runs`) supporting dual stdio/SSE transports, `.cursor/mcp.json` client configuration, and docker-compose integration. 48 unit/integration tests passing cleanly.
- [x] Phase 5 complete: Next.js 15 UI with TypeScript, Tailwind CSS, and App Router. Auto-generated TypeScript types (`scripts/generate_types.py` -> `frontend/types/api.ts`). Zustand global state (`lib/store.ts`), memory-safe WebSocket streaming subscriber (`lib/websocket.ts`), type-safe backend API fetchers (`lib/api.ts`). Responsive dark-themed navigation sidebar and header. 5 complete pages: Dashboard (`/`), Eval Runner (`/eval/new`), Run Detail Report (`/eval/[run_id]`), Model Leaderboard (`/leaderboard`) with Recharts bar chart & model recommendation oracle, Eval History (`/history`) with 2-run delta comparison modal, and Prompt Benchmark Library (`/prompts`). Production build passes with 0 errors.

## In Progress
- Transitioning to Phase 6 (Testing + Hardening)

## Phase Status
| Phase | Status |
|---|---|
| Phase 0: Pre-Build Setup | Complete |
| Phase 1A: Infrastructure | Complete |
| Phase 1B: Data Layer + Schemas | Complete |
| Phase 2: Core Eval Engine | Complete |
| Phase 3: Scoring + Feature Router | Complete |
| Phase 4: Observability + MCP | Complete |
| Phase 5: Frontend | Complete |
| Phase 6: Testing + Hardening | Next |
| Phase 7A: Extra Features Core | Not started |
| Phase 7B: Extra Features Advanced | Not started |
| Phase 8: Portfolio Polish | Not started |

## Known Problems
None.

## Next Task
Phase 6: Testing + Hardening — comprehensive end-to-end integration tests, mock server failure injection (HTTP 429 backoff, rate limits, Ollama timeout fallbacks), Celery task error recovery, and load/concurrency validation.

## Do Not Change
- ModelID enum values (LiteLLM prefix format must match exactly)
- Redis DB allocation: DB 0 = cache, DB 1 = Celery broker, DB 2 = Celery results
- Feature Middleware location: always backend/middleware/feature_router.py
- All Pydantic schemas live only in backend/schemas/ — nowhere else
