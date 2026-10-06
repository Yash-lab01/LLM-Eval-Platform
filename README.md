# 🚀 LLM Evaluation & Benchmarking Platform

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg?logo=next.js)](https://nextjs.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C.svg?logo=pytorch)](https://pytorch.org)
[![Celery](https://img.shields.io/badge/Celery-5.4+-37814A.svg?logo=celery)](https://docs.celeryq.dev)
[![Redis](https://img.shields.io/badge/Redis-7.0+-DC382D.svg?logo=redis)](https://redis.io)
[![FastMCP](https://img.shields.io/badge/FastMCP-Model_Context_Protocol-8A2BE2.svg)](https://modelcontextprotocol.io)
[![Tests Passing](https://img.shields.io/badge/tests-120%20passed-success.svg)](#-testing--code-quality)
[![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen.svg)](#-testing--code-quality)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade, self-hosted **LLM Evaluation and Benchmarking Platform** engineered for side-by-side performance evaluation, non-blocking semantic scoring, regression tracking, and observability across cutting-edge LLMs (Gemini 3.5/3.8 Flash, Groq GPT-OSS 120B/20B, Qwen 27B/32B, and local Ollama instances) — with zero paid API dependencies.

---

## 📑 Table of Contents

- [🌟 Highlights & Capabilities](#-highlights--capabilities)
- [🏛️ System Architecture](#️-system-architecture)
- [📂 Repository Structure](#-repository-structure)
- [🧩 Feature Middleware Layer (Core Architecture)](#-feature-middleware-layer-core-architecture)
- [🤖 Supported Free-Tier Model Matrix](#-supported-free-tier-model-matrix)
- [🛠️ Tech Stack Breakdown](#️-tech-stack-breakdown)
- [🚀 Quick Start](#-quick-start)
  - [Option A: Docker Compose (Recommended)](#option-a-docker-compose-recommended)
  - [Option B: Local Development Setup](#option-b-local-development-setup)
- [📡 Comprehensive API Reference](#-comprehensive-api-reference)
- [🔌 FastMCP Integration (Cursor & Claude Desktop)](#-fastmcp-integration-cursor--claude-desktop)
- [🔔 Webhook Alerts & HMAC Verification](#-webhook-alerts--hmac-verification)
- [🧪 Testing & Code Quality](#-testing--code-quality)
- [📄 License](#-license)

---

## 🌟 Highlights & Capabilities

- **⚡ Multi-Model Parallel Inference**: Stream generations simultaneously from multiple frontier models using LiteLLM as an abstraction gateway with automatic retry, exponential backoff, and jitter.
- **📡 Real-Time WebSocket Streaming**: Sub-millisecond token dispatching to a Next.js 15 frontend powered by a non-blocking Redis pub/sub backbone with guaranteed cleanup.
- **🧠 Non-Blocking PyTorch Scoring**: PyTorch BERTScore F1 running in dedicated async thread pool executors alongside ROUGE-L, latency tracking, token counters, and cost estimation.
- **🎯 Specialized AI Evaluation (RAG & Hallucination)**:
  - **Tripartite RAG Framework**: Automatically scores *Context Relevance*, *Faithfulness* (context grounding via NLI), and *Answer Relevance*.
  - **Sentence-Level NLI Hallucination Scoring**: Decomposes candidate outputs into discrete claims, cross-references source context for contradictions or ungrounded claims, and applies winner penalties.
- **⚖️ LLM-as-a-Judge (G-Eval Style)**: Automated semantic grading using Gemini 3.5 Flash across structured multi-criteria rubrics.
- **📋 9 Domain Rubrics**: Built-in Rubrics for Code Generation, Summarization, QA, Data Extraction, Creative Writing, Classification, Translation, RAG, and Command Generation with Redis persistence and custom weight balancing.
- **🔁 Regression Testing Suites**: Define prompt suites, execute automated benchmark runs, and inspect detailed score deltas (`improved`, `degraded`, `unchanged`).
- **📦 Distributed Batch Evaluation**: Ingest large-scale CSV/JSON datasets, execute via dedicated Celery worker queues (`eval_batch`), track live Redis progress, and download CSV reports.
- **📊 2D Embedding Visualizer**: Multidimensional projection (Semantic MDS / UMAP) mapping prompt, reference truth, and candidate responses on an interactive 2D coordinate plane with pairwise cosine similarity matrices.
- **📑 Executive PDF & HTML Reports**: Clean Jinja2 executive summary reports with print-ready CSS (`@media print`), score matrices, winner badges, and WeasyPrint PDF compilation.
- **🔔 Webhook Alert Dispatcher**: Evaluates threshold rules (e.g. `high_hallucination`, `latency_spike`) and dispatches async alerts with HMAC-SHA256 signature verification (`X-Eval-Signature`).
- **🔌 FastMCP Server**: Native Model Context Protocol server exposing 5 tools for Cursor IDE, Claude Desktop, and autonomous agents over `stdio` and `sse` transports.
- **🏆 Dynamic Leaderboard & Model Oracle**: Win-rate aggregation per task category with Redis caching and automated model recommendation based on task-specific Pareto efficiency.
- **🛡️ Enterprise Security & Hardening**: SlowAPI rate limiting, SHA-256 API key authentication with Redis caching, strict payload bounds, and 93%+ test coverage across 120 tests.

---

## 🏛️ System Architecture

```mermaid
flowchart TB
    subgraph Clients["Clients & Interfaces"]
        NextUI["Next.js 15 UI\n(App Router + Zustand + Tailwind)"]
        Cursor["Cursor IDE / Claude Desktop\n(FastMCP Client)"]
        ExternalAPI["External Microservices\n(REST API Clients)"]
    end

    subgraph Gateway["API & Protocol Gateway"]
        FastAPI["FastAPI Core Service (Port 8000)\n(SlowAPI Rate Limiter + SHA-256 Auth)"]
        WSHandler["WebSocket Stream Manager\n(/ws/eval/{run_id})"]
        MCP["FastMCP Server (Port 8001)\n(stdio / streamable-http SSE)"]
        FeatureRouter["Feature Middleware Router\n(Dynamic Pipeline Gating)"]
    end

    subgraph AsyncInfra["Queues, Caching & Workers"]
        RedisPubSub[("Redis (DB 0: Cache & Pub/Sub)")]
        RedisBroker[("Redis (DB 1: Celery Broker)")]
        CeleryWorker["Celery Distributed Workers\n(eval_default & eval_batch)"]
    end

    subgraph LLMGateway["Unified LLM Gateway (LiteLLM)"]
        Gemini["Google Gemini 3.5 / 3.8 Flash"]
        Groq["Groq Cloud\n(GPT-OSS 120B/20B, Qwen 27B/32B)"]
        Ollama["Local Ollama Instance"]
    end

    subgraph EvaluationCore["Scoring & Evaluation Engines"]
        BERTScore["PyTorch BERTScore Engine\n(distilbert-base-uncased / all-MiniLM)"]
        ROUGE["ROUGE-L Overlap Scorer"]
        RAGEval["RAG Tripartite Scorer\n(Context, Faithfulness, Answer)"]
        Hallucination["Sentence-Level NLI Scorer\n(DeBERTa-v3 / Entailment Heuristics)"]
        LLMJudge["LLM-as-a-Judge Engine\n(Gemini G-Eval Rubric)"]
        VisualizerEngine["Semantic 2D MDS Visualizer"]
        ReportEngine["Jinja2 & WeasyPrint Generator"]
        WebhookDispatcher["Async Webhook Alert Dispatcher"]
    end

    subgraph Storage["Persistence & Telemetry"]
        Postgres[("PostgreSQL (AsyncPG)\nRuns, Scores, Suites, Rubrics")]
        Langfuse[("Langfuse Telemetry\nTraces, Latency, Token Costs")]
    end

    NextUI <-->|HTTP / WebSocket| FastAPI
    Cursor <-->|JSON-RPC| MCP
    ExternalAPI -->|HTTP REST| FastAPI

    FastAPI --> FeatureRouter
    FastAPI <--> RedisPubSub
    FastAPI --> Postgres
    FastAPI --> WebhookDispatcher
    FastAPI --> VisualizerEngine
    FastAPI --> ReportEngine

    FeatureRouter --> LLMGateway
    FeatureRouter --> EvaluationCore

    LLMGateway --> Gemini & Groq & Ollama
    LLMGateway -.->|Async Callbacks| Langfuse

    CeleryWorker <--> RedisBroker
    CeleryWorker --> LLMGateway
    CeleryWorker --> EvaluationCore
    CeleryWorker --> Postgres
```

---

## 📂 Repository Structure

```text
├── alembic/                      # Database migrations
│   ├── versions/                 # Alembic revision scripts
│   └── env.py                    # Async migration environment
├── backend/                      # FastAPI core backend service
│   ├── api/
│   │   ├── routes/               # API domain endpoints
│   │   │   ├── batch.py          # CSV/JSON batch ingest and export
│   │   │   ├── compare.py        # Run comparison & deltas
│   │   │   ├── eval.py           # Core evaluation execution
│   │   │   ├── hallucination.py  # NLI sentence contradiction analysis
│   │   │   ├── health.py         # System health checks
│   │   │   ├── leaderboard.py    # Win rates & Pareto recommendation
│   │   │   ├── prompts.py        # Prompt versioning library
│   │   │   ├── rag.py            # RAG tripartite metric execution
│   │   │   ├── reports.py        # HTML & PDF executive report generation
│   │   │   ├── rubrics.py        # 9 domain rubrics & G-Eval judge
│   │   │   ├── suites.py         # Regression testing prompt suites
│   │   │   ├── visualizer.py     # 2D MDS scatter & similarity matrices
│   │   │   ├── webhooks.py       # Threshold alert checking & dispatch
│   │   │   └── websocket.py      # Real-time token stream subscriptions
│   │   └── dependencies.py       # API key auth & DB session injection
│   ├── core/                     # Infrastructure configuration
│   │   ├── celery_app.py         # Celery task queue setup
│   │   ├── config.py             # Pydantic-Settings environment loader
│   │   ├── database.py           # Async SQLAlchemy engine & session factory
│   │   ├── limiter.py            # SlowAPI Redis rate limiting
│   │   └── redis_client.py       # Redis async connection pool
│   ├── middleware/
│   │   └── feature_router.py     # Dynamic Feature Middleware Layer
│   ├── models/                   # SQLAlchemy ORM database models
│   ├── schemas/                  # Pydantic v2 data contracts
│   ├── services/                 # Core business & evaluation engines
│   │   ├── batch_service.py      # Async batch execution engine
│   │   ├── eval_runner.py        # Parallel multi-model runner
│   │   ├── hallucination.py      # Sentence-level NLI contradiction engine
│   │   ├── leaderboard.py        # Pareto model recommendation & ranking
│   │   ├── litellm_client.py     # LiteLLM client with backoff retries
│   │   ├── observability.py      # Langfuse session telemetry
│   │   ├── rag_eval.py           # Context, faithfulness & answer relevance
│   │   ├── reports.py            # Jinja2 & WeasyPrint compilation
│   │   ├── rubrics_and_judge.py  # Gemini G-Eval judge & rubric engine
│   │   ├── run_comparison.py     # Run delta computation
│   │   ├── scoring.py            # PyTorch BERTScore, ROUGE-L & cost estimation
│   │   ├── visualizer.py         # Semantic 2D MDS & cosine similarity
│   │   └── webhooks.py           # HMAC-SHA256 alert dispatcher
│   ├── tasks/                    # Celery background tasks
│   ├── templates/                # Jinja2 executive HTML report templates
│   ├── tests/                    # 120 automated tests (86 unit, 34 integration)
│   └── main.py                   # FastAPI lifespan application entrypoint
├── docs/                         # Architecture guides, specs & phases
├── frontend/                     # Next.js 15 Web application
│   ├── app/                      # Next.js App Router (Dashboard, Runner, Leaderboard, History)
│   ├── components/               # UI components (Sidebar, Header, Radar charts)
│   └── lib/                      # Typed API & WebSocket clients
├── mcp/                          # FastMCP Model Context Protocol server
│   └── eval_server.py            # stdio & SSE MCP tools for Cursor & Claude Desktop
├── scripts/                      # Utility scripts
│   ├── generate_types.py         # TypeScript types generator from Pydantic schemas
│   └── seed_data.py              # Database seeding script
├── docker-compose.yml            # Complete 8-service local orchestrator
└── pyproject.toml                # Project dependencies, Ruff, and Pytest configuration
```

---

## 🧩 Feature Middleware Layer (Core Architecture)

The **Feature Middleware Layer** (`FeatureRouter`) is the architectural cornerstone of this platform. It allows external consumer applications to plug in with zero pipeline bloat:

```python
from backend.middleware.feature_router import FeatureRouter
from backend.schemas.consumers import EvalConsumerConfig, FeatureFlag, ScoringMetric, TaskType

# A consumer application (e.g. AI Coding Agent) requests only latency & BERTScore:
consumer_config = EvalConsumerConfig(
    consumer_id="ai-code-assistant",
    features=[FeatureFlag.BASIC_SCORING, FeatureFlag.OBSERVABILITY],
    models=["gemini/gemini-3.5-flash", "groq/openai/gpt-oss-120b"],
    task_type=TaskType.CODE_GENERATION,
    scoring_metrics=[ScoringMetric.BERT_SCORE, ScoringMetric.LATENCY],
)

router = FeatureRouter(consumer_config)

# The pipeline dynamically gates heavy components:
if router.should_run_bert_score():
    ...  # Executes non-blocking PyTorch BERTScore
if router.should_run_hallucination():
    ...  # Skipped! No NLI overhead incurred
if router.should_run_llm_judge():
    ...  # Skipped! No extra Gemini judge call
```

### Supported Feature Flags

| Feature Flag | Description |
|---|---|
| `basic_scoring` | Computes BERTScore F1, ROUGE-L, latency, token count, and estimated cost |
| `observability` | Injects session tracking and exports execution traces to Langfuse |
| `llm_as_judge` | Triggers structured G-Eval rubric evaluation using Gemini 3.5 Flash |
| `rag_eval` | Executes tripartite RAG evaluation (Context Relevance, Faithfulness, Answer Relevance) |
| `hallucination_detection` | Decomposes response into sentences and scores NLI contradiction risk |
| `batch_eval` | Enables background file processing via Celery queues |
| `regression_testing` | Enables prompt suite comparison and regression score delta reporting |
| `custom_rubric` | Ingests custom task criteria and weights from consumer config |
| `webhook_notifications` | Evaluates score thresholds and dispatches HMAC-signed alerts |

---

## 🤖 Supported Free-Tier Model Matrix

All evaluations run exclusively on generous free-tier APIs and local open-weights instances — zero credit card required:

| Model Identifier | Provider | Category | Ideal Evaluation Tasks |
|---|---|---|---|
| `gemini/gemini-3.5-flash` | Google AI Studio | Frontier Speed / Reasoning | General QA, Code, G-Eval Rubric Judging |
| `gemini/gemini-3.8-flash` | Google AI Studio | Multimodal / Long Context | Complex Summarization, RAG Grounding |
| `groq/openai/gpt-oss-120b` | Groq Cloud | Ultra-Fast Open-Weights | Deep Reasoning, Code Generation |
| `groq/openai/gpt-oss-20b` | Groq Cloud | Low Latency / Fast Inference | Real-Time Chat, Classification |
| `groq/qwen/qwen3.8-27b` | Groq Cloud | Multilingual / Mathematics | Translation, Math, Structured Extraction |
| `groq/qwen/qwen3-32b` | Groq Cloud | Coding & Logic | Syntax Analysis, Data Transformation |
| `ollama/llama3.2` | Local Ollama Daemon | Local Edge LLM | Privacy-Sensitive QA, Offline Benchmarks |
| `ollama/mistral` | Local Ollama Daemon | Local General Purpose | Offline Reasoning, Local Extraction |
| `ollama/phi3` | Local Ollama Daemon | Compact High-Density | Lightweight Extraction, Classification |

---

## 🛠️ Tech Stack Breakdown

| Layer | Technologies |
|---|---|
| **Backend Framework** | Python 3.12, FastAPI, Pydantic v2, Pydantic-Settings, Uvicorn |
| **LLM Gateway** | LiteLLM (Gemini, Groq, Ollama) with exponential backoff & jitter |
| **Scoring & ML** | PyTorch 2.0+, HuggingFace Transformers (`distilbert-base-uncased`, `all-MiniLM-L6-v2`), ROUGE-Score |
| **Database & ORM** | PostgreSQL 16, SQLAlchemy 2.0 (AsyncIO), AsyncPG driver, Alembic migrations |
| **Caching & Queuing** | Redis 7 (DB 0: Cache/Pub-Sub, DB 1: Celery Broker, DB 2: Celery Results), Celery 5.4, Flower |
| **Observability** | Langfuse SDK v3 (automated LiteLLM success/failure callbacks & trace tagging) |
| **Agent Protocols** | FastMCP (Model Context Protocol), Anthropic MCP specification |
| **Frontend Framework** | Next.js 15 (App Router, Turbopack), React 19, TypeScript, Tailwind CSS, Lucide Icons, Recharts |
| **Security & Quality** | SlowAPI (Redis-backed), SHA-256 Auth, Ruff linter/formatter, Pre-commit hooks |

---

## 🚀 Quick Start

### Option A: Docker Compose (Recommended)

Spins up all 8 production containers (`postgres`, `redis`, `api`, `mcp`, `worker`, `flower`, `langfuse`, `frontend`):

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Yash-lab01/LLM-Eval-Platform.git
   cd LLM-Eval-Platform
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Populate GEMINI_API_KEY and GROQ_API_KEY in .env
   ```

3. **Spin up the stack:**
   ```bash
   docker compose up -d
   ```

4. **Verify running services:**
   | Service | URL / Port | Credentials / Purpose |
   |---|---|---|
   | **Frontend Web App** | [http://localhost:3001](http://localhost:3001) | Next.js 15 Benchmarking Dashboard |
   | **Backend API & Swagger** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive OpenAPI 3.1 Documentation |
   | **FastMCP Server (SSE)** | [http://localhost:8001/sse](http://localhost:8001/sse) | Streamable HTTP MCP Transport |
   | **Celery Flower Dashboard**| [http://localhost:5555](http://localhost:5555) | Worker Queue & Task Telemetry |
   | **Langfuse UI** | [http://localhost:3000](http://localhost:3000) | Observability & Trace Trees |
   | **PostgreSQL Database** | `localhost:5432` | user: `user`, password: `password`, db: `llm_eval` |
   | **Redis Server** | `localhost:6379` | Databases 0 (cache), 1 (broker), 2 (results) |

---

### Option B: Local Development Setup

#### Prerequisites
- **Python 3.12+**
- **Node.js 20+ & npm**
- **Docker** (for local PostgreSQL & Redis)

#### 1. Start Infrastructure Dependencies
```bash
docker run -d --name eval-postgres -p 5432:5432 -e POSTGRES_DB=llm_eval -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres postgres:16-alpine
docker run -d --name eval-redis -p 6379:6379 redis:7-alpine redis-server --databases 16
```

#### 2. Backend Virtual Environment & Dependencies
```bash
python -m venv .venv

# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env
```

#### 3. Database Migrations & Initial Seed
```bash
alembic upgrade head
python scripts/seed_data.py
```

#### 4. Launch Backend Services
```bash
# Terminal 1: FastAPI API Gateway
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Celery Worker
celery -A backend.core.celery_app.celery_app worker --loglevel=info -Q eval_default,eval_batch

# Terminal 3: FastMCP Protocol Server
python -m mcp.eval_server
```

#### 5. Launch Frontend
```bash
cd frontend
npm install
npm run dev
# Next.js running at http://localhost:3000
```

---

## 📡 Comprehensive API Reference

The platform provides a strictly typed OpenAPI 3.1 REST API with SlowAPI rate limiting at `/api/v1`:

| Domain | Method | Endpoint | Description |
|---|---|---|---|
| **System** | `GET` | `/health` | Verifies PostgreSQL and Redis connectivity |
| **Core Eval** | `POST` | `/api/v1/eval/run` | Dispatches parallel multi-model evaluation |
| **Core Eval** | `GET` | `/api/v1/eval/{run_id}` | Retrieves execution scores, outputs, and winner |
| **Core Eval** | `GET` | `/api/v1/eval` | Paginated list of historical evaluation runs |
| **Core Eval** | `GET` | `/api/v1/eval/compare` | Computes statistical metric deltas between two runs |
| **WebSocket** | `WS` | `/ws/eval/{run_id}` | Real-time token stream subscription channel |
| **Leaderboard** | `GET` | `/api/v1/leaderboard` | Win-rate rankings cached in Redis with TTL |
| **Leaderboard** | `GET` | `/api/v1/models/recommend` | Pareto-optimal model recommendation per task |
| **RAG Eval** | `POST` | `/api/v1/eval/rag` | Parallel multi-model RAG evaluation benchmark |
| **RAG Eval** | `POST` | `/api/v1/eval/rag/metrics` | Direct tripartite (Context, Faithfulness, Answer) scoring |
| **Hallucination**| `POST` | `/api/v1/eval/hallucination` | Sentence-level NLI contradiction & claim ungroundedness |
| **Visualizer** | `POST` | `/api/v1/visualizer/embeddings` | 2D scatter coordinates & similarity matrix |
| **Visualizer** | `GET` | `/api/v1/eval/{run_id}/visualizer` | Automated 2D projection for an evaluation run |
| **Reports** | `GET` | `/api/v1/eval/{run_id}/export/html` | Standalone print-styled executive HTML report |
| **Reports** | `GET` | `/api/v1/eval/{run_id}/export/pdf` | Executive summary PDF report export |
| **Webhooks** | `POST` | `/api/v1/webhooks/check` | Evaluates run scores against threshold alerts |
| **Webhooks** | `POST` | `/api/v1/webhooks/test` | Test dispatch webhook payload with HMAC-SHA256 signature |
| **Batch Eval** | `POST` | `/api/v1/batch/upload-file` | Ingest CSV/JSON dataset for async Celery evaluation |
| **Batch Eval** | `POST` | `/api/v1/batch/create` | Programmatically create a batch evaluation job |
| **Batch Eval** | `GET` | `/api/v1/batch/{id}` | Live batch job progress inspection |
| **Batch Eval** | `GET` | `/api/v1/batch/{id}/results` | Paginated batch prompt results |
| **Batch Eval** | `GET` | `/api/v1/batch/{id}/export` | Export completed batch results as CSV |
| **Rubrics** | `GET` | `/api/v1/rubrics` | List active domain evaluation rubrics |
| **Rubrics** | `GET` | `/api/v1/rubrics/{task_type}` | Retrieve criteria and weights for a task rubric |
| **Rubrics** | `POST` | `/api/v1/rubrics` | Register or update custom evaluation rubric |
| **Rubrics** | `POST` | `/api/v1/rubrics/judge` | Direct G-Eval semantic grading via Gemini 3.5 Flash |
| **Suites** | `POST` | `/api/v1/suites` | Create persistent prompt regression suite |
| **Suites** | `GET` | `/api/v1/suites` | List all registered regression suites |
| **Suites** | `GET` | `/api/v1/suites/{id}` | Retrieve suite details and prompts |
| **Suites** | `POST` | `/api/v1/suites/{id}/run` | Execute regression run across suite prompts |
| **Suites** | `GET` | `/api/v1/suites/{id}/runs` | Retrieve execution history for a suite |
| **Suites** | `GET` | `/api/v1/suites/{id}/regression-report` | Compare baseline vs candidate prompt suite run |

---

## 🔌 FastMCP Integration (Cursor & Claude Desktop)

The platform includes a native **FastMCP** server providing autonomous tools directly into AI agents:

### Exposed MCP Tools

1. `health_check()`: Verifies system availability.
2. `run_eval(prompt, task_type, models, ...)`: Triggers full evaluation runs directly from your editor.
3. `get_best_model(task_type, metric)`: Queries empirical leaderboard data to recommend the optimal model.
4. `get_eval_history(limit, consumer_id)`: Retrieves recent runs and winners.
5. `compare_runs(run_id_a, run_id_b)`: Computes statistical score deltas across models.

### Cursor IDE Setup

Add to your project's `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "llm-eval-platform": {
      "command": "python",
      "args": ["-m", "mcp.eval_server"],
      "cwd": "C:/Users/yashp/Desktop/LLM Eval",
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/llm_eval",
        "REDIS_CACHE_URL": "redis://localhost:6379/0"
      }
    }
  }
}
```

### Claude Desktop Setup

Add to `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "llm-eval-platform": {
      "command": "python",
      "args": ["-m", "mcp.eval_server"],
      "cwd": "C:/Users/yashp/Desktop/LLM Eval"
    }
  }
}
```

---

## 🔔 Webhook Alerts & HMAC Verification

Consumers can register alert rules (e.g. `high_hallucination` when score > 0.40, or `latency_spike` when latency > 2500ms). Webhooks are dispatched with an HMAC-SHA256 signature in the `X-Eval-Signature` header.

### Verifying Signatures

```python
import hashlib
import hmac


def verify_eval_webhook(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """Validate webhook payload integrity and authenticity."""
    expected_sig = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_sig, signature_header)
```

---

## 🧪 Testing & Code Quality

The codebase enforces strict test coverage and static analysis standards:

```bash
# Run the entire test suite (120 tests: 86 unit, 34 integration)
pytest backend/tests/ -v

# Run with test coverage report (93%+ achieved)
pytest --cov=backend --cov-report=term-missing

# Run Ruff linter and code formatting checks
ruff check .
ruff format . --check
```

### Test Suite Distribution
- **86 Unit Tests**: LiteLLM client backoff resilience, FeatureRouter permutations, PyTorch scoring thread executor, RAG tripartite metrics, sentence NLI hallucination scoring, G-Eval rubric grading, 2D MDS embedding projection, executive HTML/PDF generation, webhook HMAC signatures.
- **34 Integration Tests**: Full FastAPI REST lifecycle, WebSocket pub/sub stream cleanup, Celery eager background task processing, FastMCP JSON-RPC client interactions, SlowAPI rate limiting, and database session isolation.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
