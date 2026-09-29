# Changelog

All notable changes to the **LLM Evaluation & Benchmarking Platform** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-09-29

### Added

#### Core Evaluation Engine & Gateway (Phases 0–2)
- **Unified Multi-Model Gateway**: Integration with LiteLLM supporting parallel inference across Google Gemini 3.5/3.8 Flash, Groq Cloud (GPT-OSS 120B/20B, Qwen 27B/32B), and local Ollama instances.
- **Real-Time WebSocket Streaming**: Non-blocking token delivery to frontend clients via Redis pub/sub channels (`run:{run_id}:tokens`) with automatic connection teardown.
- **Asynchronous Task Queue**: Celery distributed workers backed by Redis broker (`eval_default` and `eval_batch` queues).
- **Data Persistence**: SQLAlchemy 2.0 async engine with PostgreSQL 16, UUID primary keys, and Alembic database versioning.
- **Security & Auth**: SHA-256 API key hashing with Redis auth caching (3600s TTL) and granular rate limiting.

#### Scoring Engine & Observability (Phases 3–4)
- **PyTorch Metric Scoring**: Asynchronous execution of BERTScore F1 (`bert-base-uncased`, `all-MiniLM-L6-v2`) via `run_in_executor` to prevent event-loop starvation.
- **Statistical Scoring Suite**: ROUGE-L n-gram overlap, time-to-first-token (TTFT), total latency, token count, and dollar cost estimation.
- **FeatureRouter Middleware**: Dynamic pipeline gating allowing consumer projects to activate only specified evaluation steps without performance overhead.
- **Dynamic Leaderboard**: SQL-aggregated win-rate rankings per task type with Redis 300s caching and Pareto-optimal model recommendation oracle.
- **Langfuse Observability**: Automated trace hooks in LiteLLM capturing model outputs, latency, tokens, cost, and consumer session groupings.
- **Run Comparison Service**: Side-by-side metric delta evaluation (`GET /api/v1/eval/compare`) across multiple runs.
- **FastMCP Protocol Server**: Model Context Protocol server exposing 5 tools (`health_check`, `run_eval`, `get_best_model`, `get_eval_history`, `compare_runs`) supporting both `stdio` (Cursor/Claude Desktop) and `sse` transports.

#### Next.js 15 Modern Frontend (Phase 5)
- **Next.js 15 App Router**: Dark-themed responsive UI built with React 19, TypeScript, and Tailwind CSS.
- **Zustand Real-time Store**: Reactive state routing token streams by model ID, tracking latencies, and rendering dynamic winner banners.
- **Automated Type Generation**: `scripts/generate_types.py` compiling Pydantic v2 schemas directly to TypeScript interfaces (`frontend/types/api.ts`).
- **Pages**:
  - `/` (Dashboard): System statistics, recent benchmark runs, and leaderboard previews.
  - `/eval/new` (Eval Runner): Multi-model selector, prompt presets, split-screen monospace streaming terminals, and gold winner celebration card.
  - `/eval/[run_id]` (Run Detail): Deep inspection of model responses, metric comparison bars, and cost breakdowns.
  - `/leaderboard` (Model Leaderboard): Recharts interactive win-rate charts, filterable tables, and recommendation oracle.
  - `/history` (Eval History): Run search, filtering, and 2-run delta comparison modal.
  - `/prompts` (Prompt Library): Curated benchmark prompts with 1-click execution.

#### Hardening & Security (Phase 6)
- **SlowAPI Rate Limiter**: Redis-backed tiered rate limits (`POST /eval/run` at 20/min, `GET /leaderboard` at 60/min, `POST /batch/upload` at 5/min).
- **Payload Guardrails**: Prompt and reference length boundaries (`max_length=50000`) preventing denial-of-service abuse.
- **Resilience Testing**: Transient HTTP 429 exponential backoff retry loops, model fallback failovers, and Redis disconnection safety.
- **Test Suite**: 77 unit and integration tests passing with 94% code coverage.

#### Extra Features: Core (Phase 7A)
- **Batch Evaluation Engine**: Upload CSV/JSON datasets, execute via Celery queue, track live progress in Redis, and download results as CSV.
- **LLM-as-a-Judge (G-Eval Style)**: Automated semantic grading using Gemini 3.5 Flash against structured rubrics with score normalization.
- **9 Domain Custom Rubrics**: Pre-configured and customizable rubrics for Code Generation, Summarization, QA, Data Extraction, Creative Writing, Classification, Translation, RAG, and Command Generation.
- **Prompt Regression Testing**: Save prompt suites, re-run against new model versions, and generate automated regression reports (`improved`, `degraded`, `unchanged`).

#### Extra Features: Specialized AI Evaluation (Phase 7B)
- **RAG Tripartite Evaluation**: Tripartite evaluation pipeline measuring:
  - *Context Relevance*: Query term alignment with retrieved passages.
  - *Faithfulness*: Grounding of generated answer against context via NLI.
  - *Answer Relevance*: Semantic matching between query and generated response.
- **Sentence-Level NLI Hallucination Detection**: Segments candidate outputs into discrete claims, flags contradictions or ungrounded statements against reference context, and applies winner penalties.

#### Extra Features: Visuals, Export & Integrations (Phase 7C)
- **2D Embedding Visualizer**: Multidimensional projection (Semantic MDS / UMAP) mapping prompt, reference, and candidate outputs to 2D coordinates `(x, y)` with pairwise cosine similarity matrix.
- **Executive Export Reports**: Jinja2 HTML reports with print-ready CSS (`@media print`) and WeasyPrint PDF compilation with graceful HTML fallback.
- **Webhook Alert Dispatcher**: Evaluates threshold alert rules (`high_hallucination`, `latency_spike`) and dispatches async HTTP POST payloads with HMAC-SHA256 signature verification (`X-Eval-Signature`).
- **TypeScript Sync**: Contracts synced for all Phase 7C data types.

#### Portfolio Polish & Release (Phase 8)
- Comprehensive `README.md` with system architecture diagram, tech badges, quick start, API reference, and FastMCP guide.
- Complete test verification with 120/120 tests passing and 93% test coverage.
- Structured `CHANGELOG.md` release notes.
