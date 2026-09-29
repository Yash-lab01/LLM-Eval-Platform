# Current State

Last updated: 2026-09-29
Current phase: Phase 8 — Portfolio Polish (Complete)

## Current Focus
All 8 phases of the LLM Evaluation & Benchmarking Platform are 100% complete, fully tested (120/120 tests passing, 93% test coverage), and pushed to remote GitHub repository.

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
- [x] Phase 7A complete: Extra Features Core:
  - EF-01 Batch Eval: CSV/JSON upload, `eval_batch` queue, Redis progress tracking, and CSV export.
  - EF-02 LLM-as-Judge: Gemini grading candidate outputs via G-eval structured rubric.
  - EF-03 Custom Rubrics: CRUD management across all 9 task categories with Redis caching.
  - EF-04 Regression Testing: Saved prompt suites, automated execution, and score delta reports.
  - Total test count expanded to 95/95 passing (93% coverage).
- [x] Phase 7B complete: Extra Features — Specialized AI Evaluation:
  - EF-05 RAG Eval Mode: Tripartite metrics (Context Relevance, Faithfulness via NLI grounding, Answer Relevance) and multi-model benchmark runner.
  - EF-06 Hallucination Scoring: Sentence-level NLI contradiction detection, claim ungroundedness scoring, and winner penalization.
  - Total test count expanded to 108/108 passing (93% coverage).
- [x] Phase 7C complete: Extra Features — Visuals, Export & Integrations:
  - EF-07 Embedding Visualizer: 2D scatter coordinates via Semantic MDS projection and pairwise cosine similarity matrix.
  - EF-08 Executive Export Reports: Jinja2 executive summary report template with responsive print styling, standalone HTML export, and WeasyPrint PDF compilation with graceful HTML fallback.
  - EF-09 Webhooks: Threshold-based alert rule evaluation (`high_hallucination`, `latency_spike`), HMAC-SHA256 signature verification (`X-Eval-Signature`), and async HTTP POST dispatching.
  - Total test count expanded to 120/120 passing (93% coverage).
- [x] Phase 8 complete: Portfolio Polish:
  - Comprehensive, portfolio-grade `README.md` with system architecture Mermaid diagram, tech badges, quick start, API reference, and FastMCP guide.
  - `CHANGELOG.md` documenting v1.0.0 release.
  - Clean git history following Rule 55 / CONVENTIONS.md.

## In Progress
None. All planned phases (Phases 0 through 8) are 100% complete and verified.

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
| Phase 7A: Extra Features Core | Complete |
| Phase 7B: Specialized AI Eval (RAG & Hallucination) | Complete |
| Phase 7C: Visuals, Export & Integrations | Complete |
| Phase 8: Portfolio Polish | Complete |

## Known Problems
None.

## Do Not Change
- ModelID enum values (LiteLLM prefix format must match exactly)
- Redis DB allocation: DB 0 = cache, DB 1 = Celery broker, DB 2 = Celery results
- Feature Middleware location: always backend/middleware/feature_router.py
- All Pydantic schemas live only in backend/schemas/ — nowhere else
