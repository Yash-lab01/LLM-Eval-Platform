# Architecture Overview

## System Architecture

```
Consumer Projects (AI Terminal Agent, Research Agent, future projects)
        │ MCP calls                    │ REST API
        ▼                              ▼
┌───────────────────┐      ┌───────────────────────┐
│   MCP Server      │      │   FastAPI Backend     │
│   port 8001       │      │   port 8000           │
│   FastMCP         │      │   Pydantic v2         │
└─────────┬─────────┘      └──────────┬────────────┘
          └────────────────┬──────────┘
                           ▼
              ┌─────────────────────────┐
              │  Feature Middleware     │
              │  feature_router.py      │
              └──────────┬──────────────┘
                         ▼
              ┌─────────────────────────┐
              │  Celery Task Queue      │
              │  Redis DB 1 (broker)    │
              │  eval_default (high)    │
              │  eval_batch (low)       │
              └──────────┬──────────────┘
                         ▼
              ┌─────────────────────────┐
              │  Eval Runner            │
              │  asyncio.gather()       │
              │  LiteLLM → Gemini       │
              │           → Groq        │
              │           → Ollama      │
              └──────────┬──────────────┘
                         │ tokens published
                         ▼
              ┌─────────────────────────┐
              │  Redis pub/sub DB 0     │
              └──────────┬──────────────┘
                         ▼
              ┌────────────────┐   ┌──────────────────────┐
              │  WebSocket     │   │  PyTorch Scorers      │
              │  /ws/eval/{id} │   │  BERTScore, ROUGE-L   │
              └───────┬────────┘   └──────────┬────────────┘
                      └──────────┬─────────────┘
                                 ▼
              ┌────────────────────────────────────┐
              │  PostgreSQL (5 tables)             │
              │  consumers, prompts, eval_runs     │
              │  model_responses, eval_scores      │
              └────────────────────────────────────┘
                                 │
              ┌────────────────┐   ┌──────────────────────┐
              │  Langfuse      │   │  Redis Cache DB 0    │
              │  self-hosted   │   │  leaderboard TTL 5m  │
              │  port 3000     │   │  api_key TTL 1h      │
              └────────────────┘   └──────────────────────┘
```

## Docker Services (8 total)

| Service | Port | Purpose |
|---|---|---|
| `api` | 8000 | FastAPI backend |
| `mcp` | 8001 | FastMCP server (streamable-http) |
| `worker` | — | Celery worker |
| `flower` | 5555 | Celery monitoring UI |
| `postgres` | 5432 | PostgreSQL 16 |
| `redis` | 6379 | Redis 7 (3 logical DBs) |
| `langfuse` | 3000 | Langfuse self-hosted |
| `frontend` | 3001 | Next.js 15 |

## Redis Key Namespace

| DB | Keys | TTL |
|---|---|---|
| DB 0 | `cache:leaderboard:{task_type}` | 5 min |
| DB 0 | `auth:apikey:{key_hash}` | 1 hour |
| DB 0 | `run:{run_id}:{model_id}` (pub/sub) | ephemeral |
| DB 1 | Celery task queue (managed by Celery) | — |
| DB 2 | Celery result backend (managed by Celery) | — |

## Data Flow: Single Eval Run

```
1. Consumer → POST /api/v1/eval/run (with EvalConsumerConfig)
2. FastAPI validates with Pydantic v2
3. FeatureRouter determines active pipeline steps
4. Celery task dispatched to eval_default queue
5. asyncio.gather() fires LiteLLM calls in parallel
6. Tokens published to Redis pub/sub as they arrive
7. WebSocket subscriber forwards tokens to browser
8. After all models done: PyTorch scorers run (via run_in_executor)
9. Scores stored in eval_scores table
10. run status updated to "completed"
11. Langfuse auto-traces all LiteLLM calls (via callbacks)
12. Leaderboard Redis cache invalidated
```
