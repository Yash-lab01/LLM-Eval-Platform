# Current State

Last updated: 2026-09-28
Current phase: Phase 7A — Extra Features Core (NEXT)

## Current Focus
Phase 6 (Testing + Security Hardening) complete with 77/77 tests passing (94% coverage). Ready to begin Phase 7A (Batch Eval, LLM-as-Judge G-eval scoring, Custom Rubrics, and Regression Test suites).

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
- [x] Phase 6 complete: Testing + Security Hardening:
  - SlowAPI rate limiting integrated with custom key resolver (`get_rate_limit_key`), resilient in-memory fallback, and custom 429 response handler (`backend/core/limiter.py`).
  - Strict payload size constraints (`max_length=50000` on prompt & reference output in `backend/schemas/eval.py`) preventing DOS abuse.
  - WebSocket full integration & lifecycle test with memory-safe cleanup (`punsubscribe` + `aclose` in finally block).
  - Celery eager execution test suite (`task_always_eager=True`).
  - Exhaustive powerset feature flag routing test suite covering all 32 combinations.
  - Chaos failure injection tests: LiteLLM transient HTTP 429 exponential backoff retry and Ollama timeout resilience.
  - Security tests: API key SHA-256 hashing, Redis auth caching (3600s TTL), and trace metadata sanitization.
  - Total test count expanded to 77/77 passing (94% coverage, exceeding 70% requirement).

## In Progress
- Transitioning to Phase 7A (Extra Features Core: Batch Eval, LLM-as-Judge, Custom Rubrics, Regression Testing)

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
| Phase 6: Testing + Hardening | Complete |
| Phase 7A: Extra Features Core | Next |
| Phase 7B: Extra Features Advanced | Not started |
| Phase 8: Portfolio Polish | Not started |

## Known Problems
None.

## Next Task
Phase 7A: Extra Features Core — EF-01 Batch Evaluation (CSV/JSON upload, `eval_batch` queue, WebSocket progress, result downloads), EF-02 LLM-as-Judge (Gemini judging models via structured G-eval rubric), EF-03 Custom Rubric Editor, and EF-04 Prompt Suite Regression Testing.

## Do Not Change
- ModelID enum values (LiteLLM prefix format must match exactly)
- Redis DB allocation: DB 0 = cache, DB 1 = Celery broker, DB 2 = Celery results
- Feature Middleware location: always backend/middleware/feature_router.py
- All Pydantic schemas live only in backend/schemas/ — nowhere else
