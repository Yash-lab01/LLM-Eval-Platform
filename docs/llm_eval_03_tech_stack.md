# LLM Eval Platform — Tech Stack

## Guiding Principles for Tech Choices
1. **Free tier only** — no paid APIs; all LLMs via free tiers or local Ollama
2. **New for you** — every tool here is one you haven't used or used less
3. **Production-grade** — not just prototyping tools; things that appear on real job descriptions
4. **Composable** — each piece works independently and together

---

## Backend

### Core Framework
| Tool | Version | Why |
|---|---|---|
| **FastAPI** | 0.115+ | You know it — but now using it *properly* with Pydantic v2, lifespan events, dependency injection |
| **Pydantic v2** | 2.x | New for you. Replaces v1. Faster, stricter, better. Every data contract uses this. |
| **Python** | 3.12 | Latest stable — use `asyncio` heavily |
| **uvicorn** | latest | ASGI server — with `--workers` for production |

**Do NOT use**: Django (too heavy), Flask (too basic for this), pydantic v1 (outdated)

---

### Async & Task Queue
| Tool | Version | Why |
|---|---|---|
| **asyncio** | stdlib | Core async — all LLM calls are async |
| **Celery** | 5.x | Background jobs: batch eval, PDF export, webhook sending |
| **Redis** | 7.x | Celery broker + result backend + WebSocket pub/sub + caching |
| **Flower** | latest | Celery task monitoring UI (great for portfolio demo) |

**Do NOT use**: threading for async work, simple Redis queues without Celery (harder to monitor)

---

### Database
| Tool | Version | Why |
|---|---|---|
| **PostgreSQL** | 16 | Primary database — all eval runs, prompts, leaderboard, API keys |
| **SQLAlchemy** | 2.x (async) | ORM with async support — `asyncpg` driver |
| **Alembic** | latest | Database migrations — version control your schema |
| **asyncpg** | latest | Async PostgreSQL driver (fastest available) |
| **Redis** | 7.x | Caching (leaderboard, API key lookup), pub/sub for WebSockets |

**Do NOT use**: SQLite (not production-grade), synchronous SQLAlchemy (kills async performance), raw SQL without ORM (hard to maintain)

---

## AI / LLM Layer

### LLM Gateway
| Tool | Version | Why |
|---|---|---|
| **LiteLLM** | latest | Single API for all models — Gemini, Groq, Ollama, HuggingFace. New for you. |
| **Langfuse SDK** | 3.x | Observability — hooks into LiteLLM callbacks automatically |

**Free models via LiteLLM**:
```python
SUPPORTED_MODELS = [
    "gemini/gemini-3.5-flash",  # Google free tier
    "gemini/gemini-3.8-flash",  # Google free tier
    "groq/openai/gpt-oss-120b",  # Groq free tier
    "groq/openai/gpt-oss-20b",  # Groq free tier
    "groq/qwen/qwen3.8-27b",  # Groq free tier
    "groq/qwen/qwen3-32b",  # Groq free tier
    "ollama/llama3.2",  # Local — free
    "ollama/mistral",  # Local — free
    "ollama/phi3",  # Local — free
]
```

**Do NOT use**: Direct Gemini SDK or Groq SDK — LiteLLM abstracts all of them. OpenAI (paid).

---

### Scoring / Eval Metrics (PyTorch)
| Tool | Version | Why |
|---|---|---|
| **PyTorch** | 2.x | Runs all local ML models for scoring |
| **bert-score** | latest | BERTScore F1 — semantic similarity to reference |
| **sentence-transformers** | latest | Embedding generation for similarity + UMAP viz |
| **rouge-score** | latest | ROUGE-L metric |
| **transformers** | 4.x | HuggingFace models for NLI (hallucination), cross-encoder |
| **umap-learn** | latest | Dimensionality reduction for embedding visualizer |

**Models used locally (PyTorch)**:
- `bert-base-uncased` — BERTScore
- `sentence-transformers/all-MiniLM-L6-v2` — fast embeddings
- `cross-encoder/nli-deberta-v3-base` — hallucination / NLI scoring

**Do NOT use**: OpenAI embeddings API (paid), spaCy alone for semantic tasks (weaker)

---

## Observability Layer

### LLM Tracing
| Tool | Version | Why |
|---|---|---|
| **Langfuse** | Self-hosted via Docker | Traces every LLM call — prompt, response, latency, cost, tokens |
| **Phoenix (Arize)** | Optional alternative | Open source, great for RAG eval tracing |

**Langfuse setup**: Runs as a Docker service alongside your app. Free, no cloud account needed.

**What gets automatically traced**:
- Every LiteLLM call → Langfuse trace
- Grouped by `consumer_id` (session)
- Token cost calculated per call
- Full prompt + response stored

**Do NOT use**: LangSmith (requires paid tier for teams), Datadog (expensive)

---

## Real-Time Communication

### WebSockets
| Tool | Why |
|---|---|
| **FastAPI WebSockets** | Built-in — no extra library needed |
| **Redis pub/sub** | Message broker between Celery workers and WebSocket server |

**Pattern**:
```
Celery Worker (running eval) → publishes to Redis channel "run:{run_id}"
WebSocket Handler → subscribes to same channel → forwards to browser
```

This decouples eval execution from WebSocket connections — multiple browser tabs can subscribe to the same run.

**Do NOT use**: Socket.io (overkill), polling (inefficient), server-sent events only (can't receive messages)

---

## MCP Layer

### MCP Server
| Tool | Version | Why |
|---|---|---|
| **mcp** (Python SDK) | latest | Official MCP SDK from Anthropic — create MCP servers |
| **FastMCP** | latest | Higher-level wrapper — less boilerplate than raw MCP SDK |

**MCP server runs as a separate FastAPI process** on port 8001, or as stdio-based server for Cursor integration.

**Do NOT use**: Custom HTTP endpoints pretending to be MCP (won't work with Cursor/Claude Desktop)

---

## Frontend

| Tool | Version | Why |
|---|---|---|
| **Next.js 15** | App Router | You've used it — use it properly with Server Components + Client Components |
| **TypeScript** | 5.x | You've used it — strict mode ON |
| **Recharts** | latest | React charting — radar charts, line charts for leaderboard |
| **Tailwind CSS** | 4.x | You've used it |
| **shadcn/ui** | latest | Component library built on Radix UI — new for you, industry standard |
| **Zustand** | latest | Lightweight state management — new for you (simpler than Redux) |

**Do NOT use**: Plain React without Next.js (loses SSR benefits), Chart.js directly (worse React integration), Redux (too heavy)

---

## Infrastructure

| Tool | Why |
|---|---|
| **Docker Compose** | Orchestrate: FastAPI + PostgreSQL + Redis + Langfuse + Celery + Frontend |
| **Alembic** | Database migrations — schema versioning |
| **.env + pydantic-settings** | Config management — Pydantic BaseSettings reads env vars with validation |

**Docker services**:
```yaml
services:
  api:           # FastAPI backend (port 8000)
  mcp:           # MCP server (port 8001 / stdio)
  worker:        # Celery worker
  flower:        # Celery monitoring (port 5555)
  postgres:      # PostgreSQL (port 5432)
  redis:         # Redis (port 6379)
  langfuse:      # Langfuse server (port 3000)
  frontend:      # Next.js (port 3001)
```

**Do NOT use**: Docker Swarm or Kubernetes for local dev, plain venv without Docker (dependency hell)

---

## Dev Tools

| Tool | Why |
|---|---|
| **Pytest + pytest-asyncio** | First project where you add tests — async test support |
| **httpx** | Async HTTP client for testing FastAPI |
| **ruff** | Linting + formatting (replaces flake8 + black) |
| **pre-commit** | Run ruff + tests before every git commit |

---

## Full Dependency List (Python)

```toml
# pyproject.toml
[tool.poetry.dependencies]
python = "^3.12"

# Core
fastapi = "^0.115"
pydantic = "^2.0"
pydantic-settings = "^2.0"
uvicorn = {extras = ["standard"], version = "*"}

# Database
sqlalchemy = {extras = ["asyncio"], version = "^2.0"}
asyncpg = "*"
alembic = "*"

# Queue
celery = "^5.0"
redis = "^5.0"
flower = "*"

# LLM
litellm = "*"
langfuse = "^3.0"

# AI/ML
torch = "^2.0"
bert-score = "*"
sentence-transformers = "*"
transformers = "^4.0"
rouge-score = "*"
umap-learn = "*"

# MCP
mcp = "*"
fastmcp = "*"

# Utility
httpx = "*"
python-multipart = "*"     # file uploads
jinja2 = "*"               # prompt templates
pandas = "*"               # batch eval CSV parsing
weasyprint = "*"           # PDF export

# Dev
pytest = "*"
pytest-asyncio = "*"
ruff = "*"
```
