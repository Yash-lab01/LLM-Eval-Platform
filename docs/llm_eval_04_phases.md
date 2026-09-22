# LLM Eval Platform — Development Phases

## Phase Overview

```
Phase 0  (Pre-Build Setup)           → Day 1–2
Phase 1A (Infrastructure)            → Week 1
Phase 1B (Data Layer + Schemas)      → Week 2
Phase 2  (Core Eval Engine)          → Week 3
Phase 3  (Scoring + Feature Router)  → Week 4
Phase 4  (Observability + MCP)       → Week 5–6
Phase 5  (Frontend)                  → Week 7–8
Phase 6  (Testing + Hardening)       → Week 9
Phase 7A (Extra Features — Core)     → Week 10–11
Phase 7B (Extra Features — Advanced) → Week 12–13
Phase 8  (Portfolio Polish)          → Week 14
```

> **Why 10 phases instead of 5?**
> Original Phase 1 had 16 tasks across 4 concerns. Phase 5 had 10 features with no priority.
> Each phase now has ONE goal and ONE verifiable deliverable.

---

## Phase 0: Pre-Build Setup
*Goal: Environment ready. Repo initialized. All tools installed. Zero code written yet.*

### Tasks
- [ ] Install Python 3.12, Poetry, Docker Desktop, Node.js 20, Git
- [ ] Create GitHub repo: `llm-eval-platform`
- [ ] Create root folder structure: `/backend` `/frontend` `/mcp` `/alembic` `/scripts` `/docs` `/context`
- [ ] Add `.gitignore` (Python, Node, .env, __pycache__)
- [ ] Get API keys: Gemini free tier + Groq free tier
- [ ] Set up Langfuse once locally to get PUBLIC_KEY + SECRET_KEY
- [ ] Read all 5 docs in `/docs/` before writing a single line of code

### Deliverable
GitHub repo exists. Folder structure created. API keys in hand. All docs read.

---

## Phase 1A: Infrastructure
*Goal: All 8 Docker services running. Zero application code.*

### Tasks
- [ ] Create `.env.example` (do this FIRST)
- [ ] Create `docker-compose.yml` with all 8 services: `api` `mcp` `worker` `flower` `postgres` `redis` `langfuse` `frontend`
- [ ] Create `docker-compose.override.yml` (volume mounts, hot reload for local dev)
- [ ] Configure Redis with 3 logical DBs: DB 0=cache/pub-sub, DB 1=Celery broker, DB 2=Celery results
- [ ] Add `gunicorn.conf.py` (4 UvicornWorkers, 0.0.0.0:8000, timeout 120)
- [ ] Set up `ruff` + `pre-commit`
- [ ] Verify: `docker-compose up` → all 8 services green. Langfuse UI at localhost:3000.

### .env.example
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_eval
REDIS_CACHE_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
GEMINI_API_KEY=
GROQ_API_KEY=
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
SECRET_KEY=
ENVIRONMENT=development
```

### Deliverable
`docker-compose up` → all services healthy. No code errors. Langfuse accessible.

---

## Phase 1B: Data Layer + Schemas
*Goal: Database tables exist. All Pydantic v2 schemas defined. Tests set up.*

### Tasks
- [ ] `backend/core/database.py` — SQLAlchemy async engine + sessionmaker (asyncpg driver)
- [ ] `backend/core/config.py` — pydantic-settings BaseSettings (reads .env with validation)
- [ ] `backend/core/celery_app.py` — Celery config (Redis DB 1/2, two queues)
- [ ] Write ALL Pydantic v2 schemas in `backend/schemas/`:
  - `models.py` → `ModelID` enum (all valid LiteLLM free-tier model strings)
  - `consumers.py` → `EvalConsumerConfig`, `FeatureFlag` enum, `ScoringMetric` enum, `TaskType` enum
  - `eval.py` → `PromptRunRequest`, `ModelResponse`, `EvalScore`, `EvalRunResult`
  - `leaderboard.py` → `LeaderboardEntry`, `ModelRecommendation`
  - `prompts.py` → `PromptCreate`, `PromptVersion`
- [ ] Write SQLAlchemy ORM models in `backend/models/`
- [ ] Write Alembic Migration 001 (5 core tables + indexes)
- [ ] Run `alembic upgrade head` → verify tables exist
- [ ] `scripts/seed_data.py` → creates 1 sample consumer + 3 sample prompts
- [ ] Set up `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"` in pyproject.toml)
- [ ] Write first tests: schema validation (5+ tests)

### Database Schema (Migration 001)
```sql
CREATE TABLE consumers (id UUID PRIMARY KEY, name VARCHAR(100), api_key VARCHAR(64) UNIQUE, config JSONB, created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE prompts (id UUID PRIMARY KEY, consumer_id UUID REFERENCES consumers(id), content TEXT, task_type VARCHAR(50), version INTEGER DEFAULT 1, parent_id UUID REFERENCES prompts(id), tags TEXT[], created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE eval_runs (id UUID PRIMARY KEY, consumer_id UUID REFERENCES consumers(id), prompt_id UUID REFERENCES prompts(id), prompt_text TEXT, task_type VARCHAR(50), models TEXT[], reference_output TEXT, status VARCHAR(20) DEFAULT 'pending', created_at TIMESTAMP DEFAULT NOW(), completed_at TIMESTAMP);
CREATE TABLE model_responses (id UUID PRIMARY KEY, run_id UUID REFERENCES eval_runs(id), model_id VARCHAR(100), output TEXT, latency_ms FLOAT, token_count INTEGER, finish_reason VARCHAR(50), from_cache BOOLEAN DEFAULT FALSE, attempt_number INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE eval_scores (id UUID PRIMARY KEY, run_id UUID REFERENCES eval_runs(id), model_id VARCHAR(100), bert_score_f1 FLOAT, rouge_l FLOAT, latency_ms FLOAT, token_count INTEGER, estimated_cost_usd FLOAT, hallucination_score FLOAT, llm_judge_score FLOAT, created_at TIMESTAMP DEFAULT NOW());
CREATE INDEX idx_eval_runs_consumer ON eval_runs(consumer_id);
CREATE INDEX idx_eval_runs_task_type ON eval_runs(task_type);
CREATE INDEX idx_eval_runs_created ON eval_runs(created_at);
CREATE INDEX idx_eval_scores_model ON eval_scores(model_id);
```

### Deliverable
`alembic upgrade head` clean. All Pydantic schemas importable. pytest passes. seed_data.py runs.

---

## Phase 2: Core Eval Engine
*Goal: POST /eval/run works. Tokens stream via WebSocket. Results stored in DB.*

### Tasks
- [ ] `backend/main.py` — FastAPI app with lifespan events (startup/shutdown)
- [ ] `GET /health` — checks DB + Redis connectivity
- [ ] `backend/services/litellm_client.py` — LiteLLM wrapper:
  - Async `call_model_stream()` with streaming
  - Retry: `autoretry_for=(RateLimitError, Timeout)`, `retry_backoff=True`, max 3
  - Metadata injection per call (run_id, consumer_id, task_type)
- [ ] `backend/services/eval_runner.py` — `run_parallel_eval()` using `asyncio.gather()`
  - Publishes tokens to Redis pub/sub: `run:{run_id}:{model_id}`
- [ ] `backend/tasks/eval_tasks.py` — Celery tasks with queue routing
- [ ] `GET /ws/eval/{run_id}` — WebSocket endpoint (with try/finally Redis cleanup)
- [ ] `POST /api/v1/eval/run` — validates → creates DB record → dispatches Celery task
- [ ] `GET /api/v1/eval/{run_id}` — returns run status + results
- [ ] Consumer API key middleware (DB lookup, cached in Redis DB 0)
- [ ] Tests: eval engine with **mocked LiteLLM** (no real API calls in tests)

### Key Patterns
```python
# Parallel runner
async def run_parallel_eval(run_id, request):
    await asyncio.gather(*[call_model_stream(run_id, m, request.prompt) for m in request.models], return_exceptions=True)
    await score_all_responses(run_id, request.reference_output)
    await update_run_status(run_id, "completed")

# WebSocket cleanup (CRITICAL — prevents Redis memory leak)
@app.websocket("/ws/eval/{run_id}")
async def ws_eval(ws, run_id):
    await ws.accept()
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(f"run:{run_id}:*")
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await ws.send_text(msg["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()

# Celery task with retry
@celery_app.task(bind=True, max_retries=3, autoretry_for=(litellm.RateLimitError, litellm.Timeout), retry_backoff=True, retry_jitter=True, queue="eval_default")
def run_eval_task(self, run_id: str): ...
```

### Deliverable
POST /eval/run → Celery fires → parallel LLM calls → tokens in WebSocket → DB updated. All tests pass with mocked LiteLLM.

---

## Phase 3: Scoring + Feature Router
*Goal: Scores computed. Feature Router live. Leaderboard queryable.*

### Tasks
- [ ] Load PyTorch models at app startup (in lifespan): `bert-base-uncased`, `all-MiniLM-L6-v2`
- [ ] `backend/services/scoring.py`:
  - `bert_score_f1()` → async via `run_in_executor` (never block event loop)
  - `rouge_l()` → direct (fast)
  - `latency_ms()`, `token_count()`, `estimated_cost_usd()` → from LiteLLM metadata
- [ ] `backend/middleware/feature_router.py` — `FeatureRouter` class (gates all scorers)
- [ ] Wire FeatureRouter into pipeline — scoring only runs if router says yes
- [ ] Leaderboard SQL: aggregate BERTScore win-rates per model per task_type
- [ ] Redis cache for leaderboard (TTL 5 min, key: `cache:leaderboard:{task_type}`)
- [ ] `GET /api/v1/leaderboard` + `GET /api/v1/models/recommend`
- [ ] Unit tests: FeatureRouter with every FeatureFlag combination

### Deliverable
Full eval run: prompt → parallel calls → scores in DB → leaderboard shows data.

---

## Phase 4: Observability + MCP
*Goal: Every LLM call in Langfuse. MCP server usable from Cursor.*

### Tasks
- [ ] `litellm.callbacks = [LangfuseHandler()]` at startup
- [ ] Consumer_id session grouping in traces
- [ ] Manually verify: token costs, latency, model visible in Langfuse dashboard
- [ ] FastMCP server (`mcp/server.py`) with dual transport:
  - `stdio` → Cursor / Claude Desktop
  - `streamable-http` port 8001 → server deployment
- [ ] 4 MCP tools: `run_eval`, `get_best_model`, `get_eval_history`, `compare_runs`
- [ ] **MCP Inspector first**: `npx @modelcontextprotocol/inspector` — verify all tools, test inputs
- [ ] Add to `.cursor/mcp.json` → test from Cursor
- [ ] Integration test: MCP tool → eval run → scores in DB

### Deliverable
All LLM calls traced in Langfuse. MCP tools work from Cursor.

---

## Phase 5: Frontend
*Goal: Next.js UI complete. Real-time streaming. Leaderboard live.*

### Tasks
- [ ] Next.js 15 + TypeScript + Tailwind + shadcn/ui
- [ ] `scripts/generate_types.py` → `frontend/types/api.ts` (run after every schema change)
- [ ] Pages (dark mode default):
  - `/` Dashboard: recent runs, quick stats
  - `/eval/new` Eval Runner: prompt + model selection + live streaming
  - `/eval/{run_id}` Run Detail: scores, responses, token breakdown
  - `/leaderboard` Model Leaderboard: table + Recharts radar chart
  - `/history` Eval History: filterable/sortable
  - `/prompts` Prompt Library
  - `/settings` Consumer config, API keys
- [ ] WebSocket client → Zustand store → routes tokens by model_id
- [ ] Zod API client (typed from generated api.ts)
- [ ] Loading skeletons + error + empty states all pages

### Deliverable
Prompt → select models → tokens stream live side-by-side → scores appear → leaderboard updates.

---

## Phase 6: Testing + Security Hardening
*Goal: 70%+ test coverage. Rate limiting. Auth solid. Production-ready.*

### Testing Tasks
- [ ] Full WebSocket test: connect → stream → disconnect → verify Redis pub/sub cleaned up
- [ ] MCP tool tests via FastMCP in-memory client
- [ ] Celery task test with `task_always_eager=True`
- [ ] Alembic migration test against test DB
- [ ] FeatureRouter: every flag combination
- [ ] BERTScore: deterministic input → expected float range
- [ ] Target: 70%+ coverage on `services/`, `middleware/`, `tasks/`

### Security Tasks
- [ ] `slowapi` Redis-backed rate limiting:
  - `POST /eval/run` → 20/min per API key
  - `GET /leaderboard` → 60/min
  - `POST /batch/upload` → 5/min
- [ ] API keys hashed before DB storage
- [ ] Request size limits (prevent giant prompt abuse)
- [ ] No keys/prompts in logs or Langfuse traces
- [ ] `.env` in `.gitignore` verified

### Deliverable
pytest 70%+ pass. Rate limiting active. Security audit clean.

---

## Phase 7A: Extra Features — Core
*Goal: Batch eval, LLM-as-judge, regression testing.*

### Tasks
- [ ] **EF-01 Batch Eval**: CSV/JSON upload → `eval_batch` queue → WebSocket progress → downloadable results
- [ ] **EF-02 LLM-as-Judge**: Gemini judges other models via structured rubric (G-eval style)
- [ ] **EF-03 Custom Rubric**: UI to define scoring criteria per task type, stored in consumer config JSONB
- [ ] **EF-04 Regression Testing**: Save prompt suite → re-run → score delta report

### Deliverable
Batch eval running. LLM-as-judge scoring. Regression suite re-runnable.

---

## Phase 7B: Extra Features — Advanced
*Goal: RAG eval, hallucination, visualizer, export, webhooks, public API.*

### Tasks
- [ ] **EF-05 RAG Eval Mode**: Context Relevance + Faithfulness + Answer Relevance (PyTorch NLI)
- [ ] **EF-06 Hallucination Score**: `nli-deberta-v3-base` sentence-level entailment (loaded at startup)
- [ ] **EF-07 Embedding Visualizer**: UMAP 2D → scatter plot in frontend
- [ ] **EF-08 Export Reports**: CSV / JSON / PDF (`weasyprint`)
- [ ] **EF-09 Webhooks**: Score threshold alerts → HTTP POST to consumer URL
- [ ] **EF-10 Public API**: Full REST + `slowapi` rate limits per API key

### Deliverable
All 10 extra features functional. Public API OpenAPI docs auto-generated.

---

## Phase 8: Portfolio Polish
*Goal: GitHub-ready. README impressive. Demo recorded. Portfolio updated.*

### Tasks
- [ ] Write `README.md`: what it is, demo GIF, quick start, architecture diagram, tech badges
- [ ] Record demo: prompt → streaming → scores → leaderboard → MCP in Cursor
- [ ] Add screenshots for every major page
- [ ] Write `CHANGELOG.md` (v1.0.0)
- [ ] Final cleanup: resolve TODOs, no dead code, correct headers
- [ ] Set repo public
- [ ] Update portfolio site + GitHub profile README

### Deliverable
Public GitHub repo. Impressive README. Portfolio updated.

---

## What Changed from Original 5 Phases

| Original | Problem | Fix |
|---|---|---|
| Phase 1 (16 tasks, 4 concerns) | Too dense, unverifiable | Split → Phase 0 + 1A + 1B |
| Phase 2 (eval + scoring mixed) | Different startup requirements | Split → Phase 2 + Phase 3 |
| No security phase | Rate limiting/auth forgotten | Added Phase 6 |
| Phase 5 (10 features, no order) | No priority, no batching | Split → Phase 7A + 7B |
| No portfolio phase | Project never "shipped" | Added Phase 8 |
