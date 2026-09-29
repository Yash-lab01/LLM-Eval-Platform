# 🚀 LLM Evaluation & Benchmarking Platform

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg?logo=next.js)](https://nextjs.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C.svg?logo=pytorch)](https://pytorch.org)
[![Celery](https://img.shields.io/badge/Celery-5.4+-37814A.svg?logo=celery)](https://docs.celeryq.dev)
[![Redis](https://img.shields.io/badge/Redis-7.0+-DC382D.svg?logo=redis)](https://redis.io)
[![FastMCP](https://img.shields.io/badge/FastMCP-Model_Context_Protocol-8A2BE2.svg)](https://modelcontextprotocol.io)
[![Tests Passing](https://img.shields.io/badge/tests-120%20passed-success.svg)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen.svg)](#testing)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade, self-hosted **LLM Evaluation and Benchmarking Platform** engineered for side-by-side performance evaluation, automated scoring, regression tracking, and observability across cutting-edge LLMs (Gemini 3.5/3.8 Flash, Groq GPT-OSS 120B/20B, Qwen 27B/32B, and local Ollama instances).

---

## 🌟 Highlights & Capabilities

- **⚡ Multi-Model Parallel Inference**: Stream generations simultaneously from multiple frontier models using LiteLLM as an abstraction gateway.
- **📡 Real-Time WebSocket Streaming**: Sub-millisecond token dispatching to a Next.js 15 frontend powered by a non-blocking Redis pub/sub backbone.
- **🧠 Non-Blocking PyTorch Scoring**: PyTorch BERTScore F1 running in dedicated async thread executors alongside ROUGE-L, latency tracking, token counters, and cost estimation.
- **🎯 Specialized AI Evaluation (RAG & Hallucination)**:
  - **Tripartite RAG Framework**: Automatically scores *Context Relevance*, *Faithfulness* (context grounding via NLI), and *Answer Relevance*.
  - **Sentence-Level NLI Hallucination Scoring**: Decomposes outputs into discrete claims, cross-references source context for contradictions or ungrounded claims, and applies winner penalties.
- **⚖️ LLM-as-a-Judge (G-Eval Style)**: Automated semantic grading using Gemini 3.5 Flash across structured multi-criteria rubrics.
- **📋 9 Domain Rubrics**: Built-in Rubrics for Code Generation, Summarization, QA, Data Extraction, Creative Writing, Classification, Translation, RAG, and Command Generation with Redis persistence and custom weight balancing.
- **🔁 Regression Testing Suites**: Define prompt suites, execute automated benchmark runs, and inspect detailed score deltas (`improved`, `degraded`, `unchanged`).
- **📦 Distributed Batch Evaluation**: Upload large-scale CSV/JSON datasets, execute via dedicated Celery worker queues (`eval_batch`), track live Redis progress, and download CSV reports.
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
        BERTScore["PyTorch BERTScore Engine\n(bert-base-uncased / all-MiniLM)"]
        ROUGE["ROUGE-L Overlap Scorer"]
        RAGEval["RAG Tripartite Scorer\n(Context, Faithfulness, Answer)"]
        Hallucination["Sentence-Level NLI Scorer"]
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

## 🛠️ Tech Stack Breakdown

| Layer | Technologies |
|---|---|
| **Backend Framework** | Python 3.12, FastAPI, Pydantic v2, Pydantic-Settings, Uvicorn |
| **LLM Gateway** | LiteLLM (Gemini, Groq, Ollama) with exponential backoff & jitter |
| **Scoring & ML** | PyTorch, HuggingFace Transformers (`bert-base-uncased`, `all-MiniLM-L6-v2`), ROUGE-Score |
| **Database & ORM** | PostgreSQL 16, SQLAlchemy 2.0 (AsyncIO), AsyncPG, Alembic migrations |
| **Caching & Queuing** | Redis 7 (Pub/Sub, Rate Limiting, Leaderboard cache), Celery 5.4 |
| **Observability** | Langfuse SDK (automated LiteLLM success/failure callbacks & trace tagging) |
| **Agent Protocols** | FastMCP (Model Context Protocol), Anthropic MCP specification |
| **Frontend Framework** | Next.js 15 (App Router, Turbopack), React 19, TypeScript, Tailwind CSS, Recharts |
| **Security & Quality** | SlowAPI (Redis-backed), SHA-256 Auth, Ruff linter/formatter, Pre-commit hooks |

---

## 🚀 Quick Start

### Option A: Docker Compose (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Yash-lab01/LLM-Eval-Platform.git
   cd LLM-Eval-Platform
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your Google Gemini / Groq API keys
   ```

3. **Spin up the entire stack:**
   ```bash
   docker compose up -d
   ```

4. **Verify running services:**
   - **Frontend UI**: [http://localhost:3000](http://localhost:3000)
   - **Backend API & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **FastMCP SSE Transport**: [http://localhost:8001/sse](http://localhost:8001/sse)
   - **PostgreSQL**: `localhost:5432`
   - **Redis**: `localhost:6379`

---

### Option B: Local Development Setup

#### Prerequisites
- **Python 3.12+**
- **Node.js 18+ & npm**
- **Docker** (for local PostgreSQL & Redis)

#### 1. Start Infrastructure Dependencies
```bash
docker run -d --name eval-postgres -p 5432:5432 -e POSTGRES_DB=llm_eval -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres postgres:16-alpine
docker run -d --name eval-redis -p 6379:6379 redis:7-alpine
```

#### 2. Backend Virtualenv & Dependencies
```bash
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env
```

#### 3. Run Database Migrations
```bash
alembic upgrade head
python scripts/seed_data.py
```

#### 4. Launch Backend Services
```bash
# Terminal 1: FastAPI API Gateway
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Celery Worker
celery -A backend.tasks.eval_tasks.celery_app worker --loglevel=info -Q eval_default,eval_batch

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

## 📡 API Reference Overview

The platform exposes an OpenAPI 3.1 compliant REST API at `/api/v1` with built-in SlowAPI rate limiting:

| Category | Method | Endpoint | Description |
|---|---|---|---|
| **Health** | `GET` | `/health` | Service liveness and dependency status |
| **Core Eval** | `POST` | `/api/v1/eval/run` | Launch parallel multi-model evaluation |
| **Core Eval** | `GET` | `/api/v1/eval/{run_id}` | Retrieve run status, scores, and winner |
| **Core Eval** | `GET` | `/api/v1/eval` | Paginated list of historical evaluation runs |
| **Core Eval** | `GET` | `/api/v1/eval/compare` | Compute metric deltas between two evaluation runs |
| **WebSocket** | `WS` | `/ws/eval/{run_id}` | Real-time token stream subscription |
| **Leaderboard**| `GET` | `/api/v1/leaderboard` | Win-rate rankings cached in Redis |
| **Leaderboard**| `GET` | `/api/v1/models/recommend`| Automated Pareto-optimal model recommendation |
| **RAG Eval** | `POST` | `/api/v1/eval/rag` | Parallel multi-model RAG evaluation benchmark |
| **RAG Eval** | `POST` | `/api/v1/eval/rag/metrics` | Direct tripartite (Context, Faithfulness, Answer) scoring |
| **Hallucination**| `POST` | `/api/v1/eval/hallucination` | Sentence-level NLI contradiction & claim ungroundedness |
| **Visualizer** | `POST` | `/api/v1/visualizer/embeddings` | 2D scatter coordinates & similarity matrix |
| **Visualizer** | `GET` | `/api/v1/eval/{run_id}/visualizer` | Automated 2D projection for an evaluation run |
| **Reports** | `GET` | `/api/v1/eval/{run_id}/export/html` | Standalone print-styled executive HTML report |
| **Reports** | `GET` | `/api/v1/eval/{run_id}/export/pdf` | Executive summary PDF report export |
| **Webhooks** | `POST` | `/api/v1/webhooks/check` | Evaluate run scores against threshold alerts |
| **Webhooks** | `POST` | `/api/v1/webhooks/test` | Test dispatch webhook payload with HMAC-SHA256 signature |
| **Batch Eval** | `POST` | `/api/v1/batch/upload-file` | Ingest CSV/JSON dataset for async evaluation |
| **Batch Eval** | `GET` | `/api/v1/batch/{id}` | Live batch progress inspection |
| **Batch Eval** | `GET` | `/api/v1/batch/{id}/export` | Export completed batch results as CSV |
| **Rubrics** | `GET` | `/api/v1/rubrics` | List active domain evaluation rubrics |
| **Rubrics** | `POST` | `/api/v1/rubrics/judge` | Direct G-Eval grading via Gemini 3.5 Flash |
| **Suites** | `POST` | `/api/v1/suites` | Create persistent prompt regression suite |
| **Suites** | `GET` | `/api/v1/suites/{id}/regression-report` | Compare baseline vs candidate prompt suite run |

---

## 🔌 FastMCP Integration (Cursor & Claude Desktop)

The platform includes a native **FastMCP** server providing autonomous tools directly into AI agents:

### Exposed MCP Tools
1. `health_check()`: Verifies system availability.
2. `run_eval(prompt, task_type, models, ...)`: Triggers full evaluation runs directly from your editor.
3. `get_best_model(task_type, metric)`: Queries empirical leaderboard data to recommend the optimal model.
4. `get_eval_history(limit)`: Retrieves recent runs and winners.
5. `compare_runs(run_id_a, run_id_b)`: Computes statistical score deltas across models.

### Cursor Setup
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
        "REDIS_URL": "redis://localhost:6379/0"
      }
    }
  }
}
```

---

## 🧪 Testing & Code Quality

The platform enforces strict code quality and test coverage standards with pre-commit gates:

```bash
# Run full test suite (120 tests)
pytest backend/tests/ -v

# Run with test coverage report
pytest --cov=backend --cov-report=term-missing

# Run Ruff linting and formatting checks
ruff check .
ruff format . --check
```

### Test Suite Distribution
- **Unit Tests**: LiteLLM client, FeatureRouter combinations, PyTorch scorers, RAG tripartite metrics, NLI hallucination detector, LLM judge, visualizer coordinates, executive reports, webhook HMAC signatures.
- **Integration Tests**: FastAPI REST endpoints, WebSocket pub/sub lifecycle, Celery eager queue execution, FastMCP client interactions, and database session lifecycles.
- **Resilience Tests**: Transient HTTP 429 backoff retry loops, model fallback failovers, and Redis disconnection safety.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
