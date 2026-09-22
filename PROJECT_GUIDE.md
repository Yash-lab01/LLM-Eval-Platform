# LLM Evaluation & Benchmarking Platform — Project Guide

> **Purpose:** This document is the source of truth for AI coding agents working on this project.
>
> **Rule:** Read this file before making architectural, structural, or significant code changes.

> **Tech Stack (locked):** Python 3.12 · FastAPI · Pydantic v2 · LiteLLM · PyTorch · Langfuse · FastMCP · PostgreSQL (asyncpg + SQLAlchemy v2) · Redis · Celery · Next.js 15 · TypeScript · Tailwind CSS · shadcn/ui · Docker Compose

> **Free-only LLMs:** Gemini 3.5/3.8 Flash (Google free tier) · Groq GPT-OSS 120B/20B, Qwen 27B/32B (Groq free tier) · Ollama local models. **No OpenAI or Anthropic API.**

---

# 1. Project Overview

## 1.1 What We Are Building

A **modular, self-hosted LLM Evaluation and Benchmarking Platform** that:

- Sends the same prompt to multiple free-tier LLMs simultaneously (Gemini, Groq, Ollama) via **LiteLLM** as a unified gateway.
- Scores responses using **PyTorch**-based BERTScore, ROUGE-L, latency, token count, and estimated cost.
- Logs every LLM call automatically to **Langfuse** (self-hosted) for full observability — traces, cost, latency per model.
- Exposes a **FastMCP server** so any other project can call the eval platform as an MCP tool from Cursor, Claude Desktop, or any MCP-compatible environment.
- Uses a **Feature Middleware Layer** so each consumer project activates only the eval features it needs — no bloat.
- Builds a **model leaderboard** from historical run data, ranked per task type.
- Stores all runs, prompts, scores, and consumer configs in **PostgreSQL** via async SQLAlchemy.
- Uses **Redis** for caching, WebSocket pub/sub, and Celery task queuing.
- Streams model tokens in real time via **WebSockets** to a **Next.js** frontend.

## 1.2 The Feature Middleware Layer (Core Architecture)

Every consumer project that plugs into this platform sends a `EvalConsumerConfig` (Pydantic v2 model) declaring:
- Which features to activate (`FeatureFlag` enum)
- Which models to use
- Which task type
- Which scoring metrics to compute

The middleware reads this config and only activates the required pipeline steps. A consumer needing only latency + BERTScore will not trigger LLM-as-judge or hallucination checks.

This is the architectural decision that makes this platform a **portfolio multiplier** — every future project can plug in without bloat.

## 1.3 Core Principle

The platform is an **evaluation system**, not a chatbot UI.

Architecture priorities:

1. Reproducibility
2. Traceability (full data lineage per score)
3. Provider abstraction via LiteLLM (never call Gemini/Groq SDK directly)
4. Feature modularity via Feature Middleware Layer
5. Deterministic configuration via Pydantic v2
6. Extensible evaluation metrics (PyTorch-based scorers are plug-in)
7. Clear separation: execution (LiteLLM) ≠ evaluation (PyTorch scorers)
8. Accurate measurement (store raw outputs, never only aggregates)
9. Prompt versioning in PostgreSQL
10. Observability via Langfuse (auto-hooked into LiteLLM callbacks)

---

# 2. Important Design Principles

## 2.1 Separation of Concerns

Keep these concepts separate:

```text
Dataset
   ↓
Evaluation Task
   ↓
Model / Application Runner
   ↓
Raw Output
   ↓
Evaluator
   ↓
Metrics
   ↓
Experiment Result
   ↓
Comparison / Report
```

Do not combine all of these into one large service or function.

---

## 2.2 Execution ≠ Evaluation

An LLM runner is responsible for obtaining an output.

An evaluator is responsible for determining how good that output is.

Example:

```text
LLM Runner
    ↓
"Paris is the capital of France."

Evaluator
    ↓
Correctness = 1.0
```

Do not put evaluation logic directly inside model-provider implementations.

---

## 2.3 Raw Results Must Be Preserved

Never store only aggregated scores.

For every evaluation run, preserve enough information to reproduce and inspect the result.

At minimum, preserve:

- Input
- Expected/reference output, when available
- Actual model output
- Model/provider
- Model parameters
- Prompt/template version
- Dataset/version
- Evaluation configuration
- Metrics
- Latency
- Token usage, if available
- Cost estimate, if available
- Timestamp
- Run/experiment ID
- Error information, if any

Aggregates can always be calculated later.

Raw outputs cannot reliably be reconstructed after the fact.

---

## 2.4 Configuration Over Hardcoding

Model configuration, evaluator configuration, dataset configuration, and experiment configuration should be represented as structured configuration.

Avoid hardcoding:

```python
model = "some-model"
temperature = 0.7
```

throughout the codebase.

Prefer centralized configuration:

```yaml
model:
  provider: openai
  name: some-model
  temperature: 0.7
```

---

## 2.5 Provider Independence via LiteLLM

**This project uses LiteLLM as the sole provider abstraction layer.** Do not call Gemini, Groq, or Ollama SDKs directly anywhere.

All model calls go through:

```python
await litellm.acompletion(model=model_id, messages=messages, stream=True)
```

Supported free-tier models (use exact string IDs):

```text
gemini/gemini-3.5-flash          ← Google free tier
gemini/gemini-3.8-flash          ← Google free tier
groq/openai/gpt-oss-120b         ← Groq free tier
groq/openai/gpt-oss-20b          ← Groq free tier
groq/qwen/qwen3.8-27b            ← Groq free tier
groq/qwen/qwen3-32b              ← Groq free tier
ollama/llama3.2                  ← Local, no API key
ollama/mistral                   ← Local, no API key
ollama/phi3                      ← Local, no API key
```

The `ModelID` enum in `backend/schemas/models.py` is the single source of truth for valid model strings. Never hardcode model names outside this enum.

LiteLLM callbacks must be configured at app startup:

```python
litellm.callbacks = [LangfuseHandler()]  # all calls auto-traced
litellm.set_verbose = False
```

---

# 3. Project Structure

**This is the actual folder structure for this project. Do not deviate from it.**

```text
llm-eval-platform/
│
├── backend/
│   ├── api/
│   │   ├── routes/             # FastAPI routers (eval, leaderboard, history, prompts)
│   │   └── middleware/         # Auth (API key), rate limiting (slowapi)
│   ├── core/
│   │   ├── config.py           # pydantic-settings BaseSettings — reads .env
│   │   ├── database.py         # SQLAlchemy async engine + sessionmaker
│   │   └── celery_app.py       # Celery app config with Redis DB 1/2
│   ├── models/                 # SQLAlchemy ORM models (NOT Pydantic — these are DB tables)
│   ├── schemas/                # Pydantic v2 schemas — ALL data contracts live here
│   │   ├── eval.py             # PromptRunRequest, EvalRunResult, EvalScore
│   │   ├── consumers.py        # EvalConsumerConfig, FeatureFlag, ScoringMetric
│   │   ├── models.py           # ModelID enum (all valid LiteLLM model strings)
│   │   ├── leaderboard.py      # LeaderboardEntry, ModelRecommendation
│   │   └── prompts.py          # PromptCreate, PromptVersion
│   ├── services/
│   │   ├── eval_runner.py      # Parallel eval orchestration (asyncio.gather)
│   │   ├── scoring.py          # PyTorch BERTScore, ROUGE-L, latency collectors
│   │   ├── litellm_client.py   # LiteLLM wrapper with retry + Langfuse callbacks
│   │   └── observability.py    # Langfuse setup and session grouping
│   ├── middleware/
│   │   └── feature_router.py   # FeatureRouter — reads EvalConsumerConfig, activates pipeline steps
│   ├── tasks/
│   │   └── eval_tasks.py       # Celery tasks (eval_default + eval_batch queues)
│   └── tests/
│       ├── unit/               # Scorer tests, feature router tests, schema validation
│       ├── integration/        # API endpoint tests (httpx async client)
│       └── fixtures/           # Mock LiteLLM responses, sample configs
│
├── mcp/
│   ├── server.py               # FastMCP server — dual transport (stdio + streamable-http)
│   └── tools/                  # Individual MCP tool implementations
│       ├── run_eval.py
│       ├── get_best_model.py
│       ├── get_eval_history.py
│       └── compare_runs.py
│
├── frontend/                   # Next.js 15 app (TypeScript + Tailwind + shadcn/ui)
│   ├── app/                    # App Router pages
│   ├── components/             # shadcn/ui + custom components
│   ├── types/
│   │   └── api.ts              # Auto-generated from Pydantic schemas (do not edit manually)
│   └── stores/                 # Zustand stores (WebSocket state)
│
├── alembic/                    # DB migrations — run via alembic upgrade head
│   └── versions/
│
├── scripts/
│   ├── generate_types.py       # Exports Pydantic → JSON Schema → frontend/types/api.ts
│   └── seed_data.py            # Seed sample consumers and prompts
│
├── docs/                       # Project documentation
│   ├── llm_eval_01_overview.md
│   ├── llm_eval_02_features.md
│   ├── llm_eval_03_tech_stack.md
│   ├── llm_eval_04_phases.md
│   └── llm_eval_05_dos_and_donts.md
│
├── docker-compose.yml          # All services (api, mcp, worker, flower, postgres, redis, langfuse, frontend)
├── docker-compose.override.yml # Local dev overrides (volume mounts, hot reload)
├── gunicorn.conf.py            # Production server config (4 UvicornWorkers)
├── pyproject.toml              # Poetry — single source of truth for dependencies
├── .env.example                # Template — copy to .env and fill in keys
├── .gitignore
├── README.md
└── PROJECT_GUIDE.md
```

---

# 4. Directory Responsibilities

## `backend/schemas/` — The Single Source of Truth for Data Contracts

Every Pydantic v2 model lives here. API request/response types, MCP tool inputs/outputs, Celery task payloads, scoring results — all defined as Pydantic models.

**Never define ad-hoc dicts in business logic. Always use a schema.**

When a schema changes, run `scripts/generate_types.py` to regenerate `frontend/types/api.ts`.

---

## `backend/middleware/feature_router.py` — The Feature Gate

This is the most important file in the project. It reads `EvalConsumerConfig` and decides which pipeline steps activate. **All feature-gating decisions go here — never scatter feature flags across services.**

---

## `backend/tasks/eval_tasks.py` — Celery Tasks

Two queues exist:
- `eval_default` — single prompt runs, high priority
- `eval_batch` — batch file processing, low priority

Celery broker uses **Redis DB 1**. Result backend uses **Redis DB 2**. General cache and pub/sub use **Redis DB 0**. Never mix these.

---

## `mcp/server.py` — MCP Entry Point

Runs as a separate process. Supports two transports:
- `stdio` → for Cursor / Claude Desktop (zero-config local)
- `streamable-http` on port 8001 → for server deployment

In stdio mode: **never print to stdout** — all logs go to stderr. stdout is the JSON-RPC channel.

---

## `alembic/` — Database Migrations

All schema changes must go through Alembic. Never use `Base.metadata.create_all()`. Run migrations with:

```bash
alembic upgrade head
```

---

# 5. `context/`

This is the project's long-term AI-readable memory.

## `context/PROJECT.md`

Contains:

- Project purpose
- Target users
- Core use cases
- Current technology stack
- Major constraints
- Non-goals
- Current maturity level

---

## `context/REQUIREMENTS.md`

Contains functional and non-functional requirements.

Example:

```text
FR-001:
The system must allow a user to create an evaluation dataset.

FR-002:
The system must execute one dataset against multiple models.

FR-003:
The system must store raw outputs.

NFR-001:
Evaluation runs should be reproducible from stored configuration.
```

Use stable requirement IDs.

---

## `context/ARCHITECTURE.md`

Contains the high-level architecture.

Example:

```text
                    ┌───────────────┐
                    │   Frontend    │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │   API Layer   │
                    └───────┬───────┘
                            │
                            ▼
                    ┌────────────────────┐
                    │ Experiment Service │
                    └─────────┬──────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
             Dataset       Runner       Evaluator
                │             │             │
                │        ┌────┴────┐        │
                │        ▼         ▼        │
                │     Providers   Local     │
                │       LLMs      Models    │
                │                           │
                └────────────┬──────────────┘
                             ▼
                       Result Storage
                             │
                             ▼
                    Comparison / Reports
```

---

## `context/DECISIONS.md`

Record important architectural decisions.

Format:

```md
## ADR-001 — Provider Abstraction

Date: YYYY-MM-DD
Status: Accepted

Decision:
Use a common provider interface.

Reason:
The platform must benchmark multiple LLM providers.

Alternatives:
- Provider-specific evaluation pipelines
- Single-provider architecture

Tradeoffs:
The abstraction adds implementation complexity but makes
the evaluation engine provider-independent.
```

Important:

**Always document WHY, not just WHAT.**

---

## `context/CURRENT_STATE.md`

This is short-term working memory.

Keep it concise.

Example:

```md
# Current State

Last updated: YYYY-MM-DD

## Current focus
Implementing evaluator registry.

## Completed
- Provider interface
- Dataset schema
- Experiment schema

## In progress
- Evaluator registry

## Known problems
- Streaming token counts are not yet captured consistently.

## Next task
Implement evaluator discovery and registration.

## Do not change
- Experiment ID format
- Result schema
```

Update this after significant work.

---

## `context/DATA_MODEL.md`

Document entities and relationships.

Core entities may include:

```text
User
Project
Dataset
DatasetVersion
DatasetItem
Model
Provider
PromptTemplate
Experiment
ExperimentRun
TestCaseResult
Evaluator
Metric
EvaluationResult
Trace
Report
```

Document:

- Purpose
- Fields
- Relationships
- IDs
- Versioning
- Required fields
- Optional fields

---

## `context/EVALUATION.md`

Document the evaluation philosophy and metric definitions.

For each metric specify:

```text
Metric name
Purpose
Input requirements
Output range
Higher/lower is better
Deterministic/non-deterministic
Reference required?
LLM-as-judge?
Known limitations
```

---

# 6. Core Service Architecture

The platform runs as multiple Docker services communicating via Redis and PostgreSQL:

```text
┌─────────────────────────────────────────────────────────────┐
│                    Consumer Projects                         │
│  (AI Terminal Agent, Research Agent, any future project)    │
└───────────────┬──────────────────────────┬──────────────────┘
                │ MCP calls                │ REST API calls
                ▼                          ▼
┌───────────────────┐          ┌───────────────────────┐
│   MCP Server      │          │   FastAPI Backend     │
│   (port 8001)     │          │   (port 8000)         │
│   FastMCP         │          │   Pydantic v2         │
└───────────┬───────┘          └───────────┬───────────┘
            │                              │
            └──────────┬───────────────────┘
                       ▼
          ┌────────────────────────┐
          │  Feature Middleware    │
          │  (feature_router.py)  │
          └────────────┬──────────┘
                       │
          ┌────────────▼──────────┐
          │   Celery Task Queue   │
          │   (Redis DB 1)        │
          │   eval_default queue  │
          │   eval_batch queue    │
          └────────────┬──────────┘
                       │
          ┌────────────▼──────────┐
          │   Eval Runner         │
          │   (asyncio.gather)    │
          │   LiteLLM → Gemini    │
          │           → Groq      │
          │           → Ollama    │
          └────┬──────────────────┘
               │ tokens streamed
               ▼
  ┌─────────────────────────┐
  │  Redis pub/sub (DB 0)   │
  └────────────┬────────────┘
               │
               ▼
  ┌─────────────────────────┐    ┌─────────────────────┐
  │  WebSocket Handler      │    │  PyTorch Scorers    │
  │  (FastAPI /ws/eval/id)  │    │  BERTScore, ROUGE-L │
  └────────────┬────────────┘    └──────────┬──────────┘
               │                            │
               ▼                            ▼
  ┌─────────────────────────────────────────────────────┐
  │              PostgreSQL                              │
  │  consumers · prompts · eval_runs                     │
  │  model_responses · eval_scores                       │
  └─────────────────────────────────────────────────────┘
               │
               ▼
  ┌─────────────────────────┐    ┌─────────────────────┐
  │  Langfuse (self-hosted) │    │  Redis Cache (DB 0) │
  │  All LLM traces auto-   │    │  Leaderboard TTL 5m │
  │  logged via LiteLLM     │    │  API key cache      │
  └─────────────────────────┘    └─────────────────────┘
```

---

# 7. Provider Layer — LiteLLM Only

**There is no custom provider class in this project.** LiteLLM IS the provider abstraction.

The `backend/services/litellm_client.py` module wraps LiteLLM with:
- Langfuse callback hooked in at startup (automatic tracing)
- Retry logic for `RateLimitError` and `Timeout` (max 3 retries, exponential backoff)
- Metadata injection per call (run_id, consumer_id, task_type)

The standardized response captured per model call (stored in `model_responses` table):

```python
class ModelResponse(BaseModel):  # schemas/eval.py
    model_id: ModelID
    output: str
    latency_ms: float
    token_count: int
    finish_reason: str
    timestamp: datetime
    from_cache: bool = False  # always record whether response was cached
    attempt_number: int = 1  # retry tracking
```

All metadata for Langfuse tracing is injected via the `metadata` parameter:

```python
await litellm.acompletion(
    model=model_id,
    messages=messages,
    metadata={
        "run_id": str(run_id),
        "consumer_id": consumer_id,
        "task_type": task_type,
        "generation_name": f"eval-{model_id}",
    },
)
```

Do not add new model providers by writing custom SDK integrations. Add them as a new `ModelID` enum value with the correct LiteLLM prefix.

---

# 8. Scoring Architecture (PyTorch-based)

All scoring happens in `backend/services/scoring.py`. Scorers are activated by the **Feature Middleware Layer** — do not call scorers directly from route handlers or Celery tasks.

## Implemented Scorers

```text
scoring.py
├── bert_score_f1()      ← PyTorch + bert-score library (requires reference_output)
├── rouge_l()            ← rouge-score library
├── latency_ms()         ← collected during LiteLLM call
├── token_count()        ← from LiteLLM response metadata
├── estimated_cost()     ← LiteLLM cost calculation
├── hallucination_nli()  ← PyTorch cross-encoder/nli-deberta-v3-base [Phase 5]
└── llm_judge()          ← Gemini-based G-eval style scoring [Phase 5]
```

## Critical Rules for Scorers

1. **PyTorch models are loaded ONCE at app startup** — never inside a scoring function call (too slow).
2. **All PyTorch scoring runs in `run_in_executor`** — never block the async event loop.
3. **BERTScore requires a `reference_output`** — the Feature Middleware validates this before activating the scorer.
4. Each scorer returns a typed Pydantic model, never a raw float:

```python
class EvalScore(BaseModel):  # schemas/eval.py
    model_id: ModelID
    bert_score_f1: float | None  # None if no reference_output provided
    rouge_l: float | None
    latency_ms: float
    token_count: int
    estimated_cost_usd: float
    hallucination_score: float | None  # None unless FeatureFlag.HALLUCINATION_CHECK active
    llm_judge_score: float | None  # None unless FeatureFlag.LLM_AS_JUDGE active
```

## Adding a New Scorer

1. Add a function to `scoring.py`
2. Add a `FeatureFlag` or `ScoringMetric` enum value in `schemas/consumers.py`
3. Add a `should_run_X()` check in `feature_router.py`
4. Add a column to the `eval_scores` DB table + Alembic migration
5. Write a unit test mocking the scorer

---

# 9. Evaluation Types

The architecture should be able to support multiple evaluation styles.

## 9.1 Reference-Based

Input:

```text
Prompt
Expected answer
Model answer
```

Examples:

- Exact match
- BLEU
- ROUGE
- Semantic similarity

---

## 9.2 Reference-Free

Input:

```text
Prompt
Model answer
```

Examples:

- Toxicity
- Safety
- Style
- Some relevance evaluators

---

## 9.3 LLM-as-a-Judge

Input:

```text
Prompt
Model output
Optional reference
Evaluation rubric
```

The judge model produces:

```text
Score
Reason
Optional structured feedback
```

Store the judge model and judge configuration.

A judge result must never be treated as inherently objective.

Record:

- Judge model
- Judge prompt/rubric
- Judge temperature
- Judge version/configuration
- Raw judge response
- Parsed score
- Parsing errors

---

## 9.4 Pairwise Evaluation

Compare:

```text
Model A output
Model B output
```

The result should preserve:

```text
winner / preference
reason
judge
confidence, if supported
```

Avoid reducing pairwise comparisons to a single ranking without preserving the original comparisons.

---

# 10. Experiment Model

An experiment represents an intentional evaluation configuration.

Conceptually:

```text
Experiment
│
├── Dataset
│   └── Dataset Version
│
├── Prompt
│   └── Prompt Version
│
├── Models
│   ├── Model A
│   ├── Model B
│   └── Model C
│
├── Evaluators
│   ├── Accuracy
│   ├── Relevance
│   └── Latency
│
└── Execution Configuration
    ├── temperature
    ├── max_tokens
    ├── concurrency
    └── seed
```

An experiment should be reproducible from its configuration.

---

# 11. Experiment Run

Distinguish:

```text
Experiment
    ↓
Experiment Run
```

Example:

```text
Experiment:
"Compare 3 models on customer-support dataset"

Run #1:
2026-09-20

Run #2:
2026-09-21
```

The experiment defines **what should be tested**.

The run records **what actually happened**.

---

# 12. Test Case Result

Every individual test case should ideally produce a record containing:

```text
run_id
dataset_id
dataset_version
test_case_id

model
provider
model_version/configuration

prompt
rendered_prompt

input

reference_output

actual_output

input_tokens
output_tokens
total_tokens

latency
time_to_first_token
throughput

cost

evaluation_results

status
error

timestamp
```

Do not discard failed test cases.

A failed request is itself useful evaluation data.

---

# 13. Benchmark Dimensions

The platform should distinguish different dimensions rather than treating "best model" as one universal number.

## Quality

Examples:

- Correctness
- Relevance
- Faithfulness
- Groundedness
- Semantic similarity
- Instruction following
- Safety
- Toxicity
- Structured output validity

## Performance

Examples:

- Total latency
- Time to first token
- Tokens/sec
- Requests/sec
- Concurrency behavior

## Cost

Examples:

- Input token cost
- Output token cost
- Cost per request
- Cost per successful task
- Estimated cost per 1K / 1M tokens

## Reliability

Examples:

- Error rate
- Timeout rate
- JSON/schema failure rate
- Retry rate
- Provider availability

Never combine all dimensions into one score unless the user explicitly defines a weighting methodology.

---

# 14. Dataset Versioning

Datasets must be versioned.

Bad:

```text
dataset.csv
```

Better:

```text
customer_support/
├── v1/
├── v2/
└── v3/
```

or use database/object-storage version identifiers.

A run must reference the exact dataset version used.

If a dataset changes, create a new version.

Do not silently mutate a dataset used by previous experiments.

---

# 15. Prompt Versioning

Prompts are part of the experiment configuration.

Track:

```text
prompt_id
prompt_version
template
variables
system_prompt
user_prompt
created_at
```

Changing a prompt should make the experiment configuration distinguishable.

Otherwise model comparisons become invalid.

---

# 16. Reproducibility

Every run should capture:

```text
Dataset version
Prompt version
Model
Provider
Model parameters
Evaluator versions
Judge model
Application version / Git commit
Environment/configuration
Random seed, where applicable
Timestamp
```

Whenever practical, record the Git commit hash.

A result should answer:

> "Exactly what produced this score?"

---

# 17. Evaluation Workflow

The standard workflow is:

```text
1. Define dataset
        ↓
2. Version dataset
        ↓
3. Define prompt/task
        ↓
4. Select models/providers
        ↓
5. Select evaluators
        ↓
6. Create experiment
        ↓
7. Validate configuration
        ↓
8. Execute test cases
        ↓
9. Capture raw outputs
        ↓
10. Calculate metrics
        ↓
11. Store results
        ↓
12. Aggregate results
        ↓
13. Compare runs/models
        ↓
14. Generate report
```

---

# 18. Execution Pipeline

A run should conceptually work like:

```text
Experiment
    ↓
Load Dataset
    ↓
Validate Configuration
    ↓
Create Run
    ↓
For each test case
    ↓
Render Prompt
    ↓
Call Model
    ↓
Capture Response + Telemetry
    ↓
Run Evaluators
    ↓
Store Test Case Result
    ↓
Aggregate Metrics
    ↓
Finalize Run
```

Do not aggregate first and discard individual results.

---

# 19. Error Handling

Errors should be classified.

Example:

```text
ProviderError
RateLimitError
AuthenticationError
TimeoutError
InvalidResponseError
ParsingError
EvaluationError
DatasetError
ConfigurationError
```

A failed test case should look something like:

```json
{
  "status": "failed",
  "error": {
    "type": "TimeoutError",
    "message": "...",
    "retryable": true
  }
}
```

Do not silently convert errors to score `0`.

A timeout is not necessarily the same thing as an incorrect answer.

---

# 20. Retry Policy

Retries should be explicit and recorded.

Track:

```text
attempt_number
retry_reason
retry_timestamp
```

Do not hide retries inside provider code.

The final result should indicate whether the request succeeded after retries.

---

# 21. Concurrency

Benchmarking systems need careful concurrency handling.

Separate:

```text
Sequential evaluation
Parallel evaluation
Rate-limited evaluation
```

Do not increase concurrency without considering:

- Provider rate limits
- Local GPU memory
- API quotas
- CPU usage
- Network bandwidth
- Database load

Concurrency configuration must be part of the run metadata.

---

# 22. Metrics Storage

Store raw metric results.

Example:

```json
{
  "metric": "correctness",
  "score": 0.9,
  "max_score": 1.0,
  "passed": true,
  "evaluator_version": "1.2",
  "metadata": {}
}
```

Aggregations such as:

```text
mean
median
p95
min
max
standard deviation
pass rate
```

should be calculated from raw results.

---

# 23. Statistical Considerations

Avoid declaring a model better from tiny samples.

For benchmark comparisons, consider:

- Sample size
- Mean
- Median
- Variance
- Confidence intervals where appropriate
- Per-category performance
- Failure rates
- Outliers
- Statistical significance where appropriate

Always expose the underlying sample size.

A score of `0.92` based on 10 examples should not be presented the same way as `0.92` based on 10,000 examples.

---

# 24. Model Comparison

A comparison should support:

```text
Model
Quality
Latency
Cost
Error rate
Throughput
Token usage
```

But avoid hiding tradeoffs behind one universal ranking.

Users should be able to inspect the underlying metrics.

Example:

```text
Model A
Quality: 0.91
Latency: 1.2s
Cost: $0.004/request

Model B
Quality: 0.87
Latency: 0.4s
Cost: $0.001/request
```

The platform reports the measurements; the user decides what tradeoff matters.

---

# 25. LLM-as-Judge Best Practices

Treat judge-based evaluation as its own model invocation.

Store:

```text
judge_model
judge_provider
judge_prompt
judge_rubric
judge_temperature
judge_output
parsed_score
parsing_status
```

If possible, support:

```text
single judge
multiple judges
pairwise judge
reference-based judge
rubric-based judge
```

Do not assume judge scores are ground truth.

---

# 26. RAG Evaluation

The architecture should eventually support RAG-specific evaluation.

Separate:

```text
Retrieval Evaluation
+
Generation Evaluation
```

Retrieval metrics may include:

```text
Context Precision
Context Recall
Hit Rate
MRR
NDCG
Recall@K
Precision@K
```

Generation metrics may include:

```text
Faithfulness
Answer Relevance
Correctness
Groundedness
```

Capture retrieved documents/chunks for every test case when privacy and storage constraints permit.

A RAG result should be traceable:

```text
Query
 ↓
Retrieved chunks
 ↓
Prompt context
 ↓
LLM output
 ↓
Evaluation
```

---

# 27. Agent Evaluation

For future agent support, do not only evaluate the final answer.

Capture:

```text
Input
 ↓
Agent reasoning/tool calls
 ↓
Tool inputs
 ↓
Tool outputs
 ↓
Intermediate actions
 ↓
Final response
```

Useful metrics may include:

- Task success
- Tool-call correctness
- Tool-call efficiency
- Invalid tool calls
- Number of steps
- Latency
- Cost
- Final answer quality

Do not expose hidden chain-of-thought as a required evaluation artifact.

Store observable actions, tool calls, and outputs instead.

---

# 28. Observability

Every important operation should have structured logs.

Use:

```text
request_id
run_id
experiment_id
test_case_id
provider
model
timestamp
duration
status
```

Logs should make it possible to answer:

> "What happened during this specific failed evaluation?"

---

# 29. Secrets

Never commit `.env` or any file containing real API keys.

The `.env.example` for this project:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_eval

# Redis (3 separate DBs — do NOT mix these)
REDIS_CACHE_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# LLM APIs (free tiers only — no OpenAI, no Anthropic)
GEMINI_API_KEY=
GROQ_API_KEY=

# Langfuse (self-hosted — no cloud account needed)
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=

# App
SECRET_KEY=
ENVIRONMENT=development
```

`backend/core/config.py` uses `pydantic-settings BaseSettings` to read all env vars with validation. **All config access must go through this class — never `os.getenv()` directly.**

Never print API keys or tokens in logs or Langfuse traces.

---

# 30. Testing Strategy

**Framework**: `pytest` + `pytest-asyncio` (configured with `asyncio_mode = "auto"` in `pyproject.toml`).
**HTTP client for FastAPI tests**: `httpx` async client.
**Never make real LiteLLM API calls in tests** — always mock.

## Unit Tests (`backend/tests/unit/`)

Test:
- Feature Middleware (feature_router.py) — most critical, test all flag combinations
- Pydantic v2 schema validation (especially `model_validator` cross-field checks)
- Scoring functions (BERTScore, ROUGE-L) with deterministic inputs
- Cost calculation logic
- ModelID enum validation

## Integration Tests (`backend/tests/integration/`)

Test:
- `POST /api/v1/eval/run` — full flow with mocked LiteLLM
- WebSocket streaming — connect, receive tokens, disconnect (test cleanup)
- MCP tools — call via FastMCP in-memory client
- Celery task dispatch + result retrieval (use `task_always_eager=True` in test config)
- Alembic migrations — run against a test DB

## Regression Tests

When a bug is found:
1. Write a failing test that reproduces it.
2. Fix the bug.
3. Keep the test permanently.

## What NOT to Test
- Don't test LiteLLM internals (it's a dependency, not our code)
- Don't test Langfuse SDK internals
- Don't make live API calls in CI

## MCP-Specific Testing

Before testing in Cursor:
```bash
npx @modelcontextprotocol/inspector
# Point at mcp/server.py, verify all tools appear, test each tool with sample inputs
```

---

# 31. Test Fixtures

Keep small deterministic fixtures.

Example:

```text
tests/fixtures/
├── datasets/
├── model_responses/
├── evaluator_outputs/
└── configs/
```

Do not depend on live APIs for ordinary unit tests.

Mock provider responses where appropriate.

---

# 32. Development Workflow for AI Agents

Every meaningful task should follow this workflow.

```text
STEP 1
Read:
- PROJECT_GUIDE.md
- context/CURRENT_STATE.md
- relevant context files

STEP 2
Inspect the existing implementation.

STEP 3
Identify affected components.

STEP 4
Before coding, explain the intended change internally/briefly.

STEP 5
Make the smallest reasonable change.

STEP 6
Run relevant tests.

STEP 7
Inspect the resulting diff.

STEP 8
Fix regressions.

STEP 9
Update documentation/context.

STEP 10
Update CURRENT_STATE.md.

STEP 11
Record an ADR if an architectural decision was made.

STEP 12
Record an experiment if an approach was tested.
```

---

# 33. Rules for AI Coding Agents

## Rule 1 — Do Not Rewrite Unnecessarily

Do not rewrite working modules simply because a different implementation looks cleaner.

---

## Rule 2 — Inspect Before Modifying

Before changing a component:

1. Find its usages.
2. Understand its interface.
3. Inspect related tests.
4. Check relevant architecture decisions.

---

## Rule 3 — Preserve Existing Contracts

Do not silently change:

- API response formats
- Database schemas
- Experiment identifiers
- Result schemas
- Evaluator interfaces
- Provider interfaces

If a breaking change is necessary, document it.

---

## Rule 4 — Do Not Add Dependencies Casually

Before adding a dependency:

1. Check whether the project already provides equivalent functionality.
2. Check whether the dependency is necessary.
3. Consider maintenance and security implications.
4. Record the reason if it materially affects architecture.

---

## Rule 5 — Do Not Invent APIs

Do not assume provider SDK behavior.

Check the installed version/documentation or existing implementation.

---

## Rule 6 — Never Hide Errors

Do not use:

```python
except:
    pass
```

or equivalent silent failure patterns.

---

## Rule 7 — Do Not Delete Unknown Code

If code appears unused but its purpose is unclear:

- investigate it,
- search for references,
- inspect history if available,
- document the finding.

Do not immediately delete it.

---

## Rule 8 — Update Context After Significant Changes

If architecture, behavior, dependencies, schemas, or evaluation methodology changes, update the relevant documentation.

---

# 34. Experiment Tracking

Each significant benchmark experiment should have a record.

Example:

```text
experiments/
└── 2026-09-22-rag-model-comparison/
    ├── README.md
    ├── config.yaml
    ├── results.json
    └── report.md
```

README:

```md
# Experiment

## Goal
Compare models on RAG question answering.

## Dataset
customer_qa v3

## Models
- Model A
- Model B
- Model C

## Evaluators
- Correctness
- Faithfulness
- Latency

## Configuration
See config.yaml.

## Result
See results.json.

## Conclusion
Document factual observations only.
```

---

# 35. Research Records

When researching a technology, model, evaluator, or architecture, record useful findings.

Example:

```text
context/research/
├── embedding-models.md
├── llm-providers.md
├── judge-models.md
└── vector-databases.md
```

Record:

- What was investigated
- Date
- Sources
- Findings
- Decision
- Limitations

Do not treat temporary web findings as permanent truth without considering their date/version.

---

# 36. Known Issues

Maintain:

```text
context/issues/KNOWN_ISSUES.md
```

Format:

```md
## ISSUE-014 — Token counts differ between providers

Status: Open
Severity: Medium

Description:
Provider A reports estimated token usage while Provider B
reports exact usage.

Impact:
Cross-provider cost comparisons may not be perfectly equivalent.

Current workaround:
Mark token source as estimated/exact.

Planned solution:
Normalize usage metadata.
```

---

# 37. Changelog

Use `CHANGELOG.md` for meaningful user-facing changes.

Example:

```md
## [0.3.0] - YYYY-MM-DD

### Added
- Dataset versioning
- Pairwise model comparison

### Changed
- Updated evaluator interface

### Fixed
- Incorrect latency calculation
```

Do not use the changelog as a substitute for technical decision records.

---

# 38. README vs Context

Use them differently.

## README.md

For humans who want to understand/use the project quickly.

Contains:

- What it is
- Features
- Installation
- Quick start
- Basic usage

## PROJECT_GUIDE.md

For AI agents and maintainers.

Contains:

- Architecture
- Rules
- Workflow
- Project structure
- Evaluation methodology
- Documentation expectations

## context/

For evolving project-specific knowledge.

---

# 39. Definition of Done

A task is not complete merely because the code works.

A meaningful feature is complete when:

```text
[ ] Implementation completed
[ ] Relevant tests added/updated
[ ] Existing tests pass
[ ] Error handling considered
[ ] Configuration updated if needed
[ ] Documentation updated
[ ] Context updated
[ ] CURRENT_STATE.md updated
[ ] ADR created if architecture changed
[ ] Experiment documented if applicable
[ ] Git diff reviewed
```

---

# 40. Before Starting a New Feature

Ask:

```text
1. Does this feature already partially exist?
2. Which layer should own it?
3. Does it require a new abstraction?
4. Does it change an existing interface?
5. Does it require a database migration?
6. Does it require new tests?
7. Does it affect reproducibility?
8. Does it affect experiment comparability?
9. Does it require documentation?
```

---

# 41. Before Refactoring

Always determine:

```text
What problem does the refactor solve?

What behavior must remain unchanged?

What tests protect that behavior?

What dependencies use this code?

Can the refactor be split into smaller changes?
```

Do not refactor unrelated code during feature work unless necessary.

---

# 42. Evaluation Integrity Rules

The platform exists to measure systems accurately.

Therefore:

1. Never silently change evaluation criteria.
2. Version evaluators when their behavior changes materially.
3. Preserve raw outputs.
4. Preserve dataset versions.
5. Preserve prompt versions.
6. Record model configuration.
7. Record judge configuration.
8. Distinguish failed requests from incorrect responses.
9. Distinguish estimated metrics from exact metrics.
10. Never present aggregated scores without sample size.
11. Preserve enough information to reproduce a run.
12. Never modify historical results to reflect newer evaluation logic.

If an evaluator changes, old results should remain associated with the old evaluator version.

---

# 43. Data Lineage

Every score should be traceable backwards:

```text
Score
 ↓
Metric Result
 ↓
Test Case Result
 ↓
Model Output
 ↓
Prompt
 ↓
Dataset Item
 ↓
Dataset Version
 ↓
Experiment Run
 ↓
Experiment Configuration
```

This is one of the most important architectural requirements.

If a score cannot be traced back to the original model output and configuration, the evaluation system has lost important provenance.

---

# 44. Versioning Strategy

Version these independently where practical:

```text
Dataset
Prompt
Evaluator
Model configuration
Experiment
Application
```

Example:

```text
Dataset:      customer_qa@v3
Prompt:       support_prompt@v5
Evaluator:    correctness@v2
Model:        model-x@config-7
Application:  git:a81f92c
Experiment:   exp_2026_09_22_001
```

---

# 45. Security and Privacy

Evaluation datasets may contain sensitive information.

The architecture should eventually support:

- Dataset access control
- Project-level isolation
- Secret management
- PII detection/redaction
- Audit logs
- Data retention policies
- Secure storage

Do not log sensitive prompts or outputs indiscriminately.

---

# 46. Performance Principles

Do not optimize prematurely.

First establish:

```text
Correctness
Reproducibility
Observability
```

Then optimize:

```text
Concurrency
Caching
Batching
Database queries
Vector search
Provider calls
```

Benchmark platform performance separately from LLM performance.

Do not accidentally include UI/API/database overhead when claiming to measure raw model latency unless that is explicitly the metric.

---

# 47. Caching

Caching can make benchmarks invalid if implemented carelessly.

If caching is used:

- Record whether a response came from cache.
- Allow caching to be disabled.
- Include cache configuration in experiment metadata.
- Never compare cached and uncached runs without making the distinction clear.

For model benchmarking, raw model execution and cached application behavior should be treated as separate measurements.

---

# 48. Cost Tracking

Cost calculations should be provider/model/configuration specific.

Store:

```text
input_tokens
output_tokens
input_price
output_price
estimated_cost
currency
pricing_version
```

Do not hardcode prices throughout the application.

Pricing changes over time.

Record the pricing version/date used to calculate a result.

---

# 49. UI Principles

The dashboard should allow users to move from:

```text
Experiment
    ↓
Run
    ↓
Model
    ↓
Metric
    ↓
Test Case
    ↓
Raw Output / Trace
```

A user should be able to answer:

> "Why did this model receive this score?"

without digging through application logs.

---

# 50. Development Phases (This Project)

See `docs/llm_eval_04_phases.md` for full task lists. Summary:

```text
Phase 1 — Foundation (Week 1-2)
├── Docker Compose with all 8 services
├── .env.example + pydantic-settings config
├── PostgreSQL + Alembic migration 001 (5 core tables)
├── Redis (3 DBs: cache/pub-sub/broker/result)
├── Celery + Flower (eval_default + eval_batch queues)
├── All Pydantic v2 schemas defined upfront
├── FastAPI health check endpoint
├── pytest setup + ruff + pre-commit
└── Langfuse self-hosted in Docker

Phase 2 — Core Eval Engine (Week 3-4)
├── LiteLLM integration (all free models)
├── Parallel eval runner (asyncio.gather)
├── WebSocket streaming with Redis pub/sub
├── WebSocket disconnect cleanup (try/finally)
├── Celery eval tasks with retry/backoff
├── PyTorch BERTScore + ROUGE-L scorers
├── POST /api/v1/eval/run + GET /api/v1/eval/{run_id}
└── Full pytest coverage (mocked LiteLLM)

Phase 3 — Observability + MCP (Week 5-6)
├── Langfuse + LiteLLM callback integration
├── Feature Middleware Layer
├── FastMCP server (dual transport: stdio + HTTP)
├── MCP Inspector testing → Cursor testing
├── Redis caching for leaderboard + API keys
└── Integration test: MCP tool → eval run → scores

Phase 4 — Frontend (Week 7-8)
├── Next.js 15 + shadcn/ui
├── scripts/generate_types.py (Pydantic → Zod)
├── Eval runner page (live streaming side-by-side)
├── Leaderboard page (Recharts radar chart)
├── Eval history + run detail pages
├── Prompt library page
└── Zustand WebSocket state

Phase 5 — Extra Features (Week 9-12)
├── EF-01: Batch eval (CSV/JSON → eval_batch queue)
├── EF-02: LLM-as-judge (Gemini G-eval)
├── EF-04: Regression testing (prompt suites)
├── EF-05: RAG eval mode
├── EF-06: Hallucination score (DeBERTa NLI)
├── EF-08: Export reports (CSV/JSON/PDF)
└── EF-10: Public API + slowapi rate limiting
```

Build the Feature Middleware Layer and Pydantic schemas in Phase 1 — everything else depends on them.

---

# 51. The Core Loop Must Remain Simple

The fundamental system should be understandable as:

```text
Dataset
    +
Model
    +
Prompt
    +
Evaluator
    ↓
Experiment Run
    ↓
Raw Results
    ↓
Metrics
    ↓
Comparison
```

If the architecture becomes so complicated that this flow is difficult to identify, reconsider the design.

---

# 52. AI Agent Context Loading Strategy

Do not force an AI agent to read every document on every request.

Recommended strategy:

## Always read

```text
PROJECT_GUIDE.md
context/PROJECT.md
context/CURRENT_STATE.md
context/CONVENTIONS.md
```

## For architecture changes

Also read:

```text
context/ARCHITECTURE.md
context/DECISIONS.md
context/DATA_MODEL.md
```

## For evaluator work

Also read:

```text
context/EVALUATION.md
context/DECISIONS.md
relevant evaluators/
```

## For provider work

Also read:

```text
context/ARCHITECTURE.md
context/DECISIONS.md
relevant provider implementation
```

## For bug fixes

Also read:

```text
context/issues/KNOWN_ISSUES.md
relevant tests
relevant implementation
```

## For experiments

Also read:

```text
context/experiments/
experiments/configs/
```

This keeps agent context focused and reduces unnecessary token usage.

---

# 53. Context Update Protocol

After completing significant work, the AI agent should ask:

```text
Did I learn something that future agents need to know?
```

If yes, update the appropriate file.

Use this mapping:

```text
New requirement
        → REQUIREMENTS.md

Architecture change
        → ARCHITECTURE.md + DECISIONS.md

Important implementation convention
        → CONVENTIONS.md

Current progress
        → CURRENT_STATE.md

Failed approach
        → issues/ or experiments/

Benchmark result
        → experiments/

Known bug
        → KNOWN_ISSUES.md

Resolved bug
        → RESOLVED_ISSUES.md

User-facing change
        → CHANGELOG.md
```

Do not dump every minor coding detail into the context folder.

The goal is **useful memory, not documentation noise**.

---

# 54. What NOT To Do

```text
❌ Call Gemini/Groq/Ollama SDK directly — always use LiteLLM
❌ Use OpenAI or Anthropic API (no paid keys)
❌ Put scoring logic inside API route handlers
❌ Load PyTorch models inside a request handler (load at startup)
❌ Run PyTorch scoring synchronously (use run_in_executor)
❌ Mix Redis DB 0 / DB 1 / DB 2 (cache / Celery broker / Celery results)
❌ Use in-memory rate limiting with multiple uvicorn workers (use slowapi + Redis)
❌ Print to stdout in MCP stdio mode (corrupts JSON-RPC stream)
❌ Scatter feature flags across services (all gating in feature_router.py)
❌ Skip Alembic and use create_all() for schema changes
❌ Manually edit frontend/types/api.ts (it's generated from Pydantic schemas)
❌ Store only aggregate scores — always preserve raw model_responses
❌ Hardcode model name strings — always use ModelID enum
❌ Store real API keys in .env.example or commit .env
❌ Make real LiteLLM API calls in tests — always mock
❌ Test MCP in Cursor before verifying with MCP Inspector first
❌ Skip WebSocket disconnect cleanup (Redis pub/sub subscription leak)
❌ Ignore Celery retry logic for LLM calls (rate limits are real)
❌ One giant service file — keep eval_runner, scoring, litellm_client, observability separate
❌ Rewrite working modules without a documented reason
❌ Mix backend + frontend + docs changes in one git commit (one scope per commit)
❌ Write a vague commit message like "updates" or "fix stuff"
```

---

# 55. Git Commit Convention

> Full reference: `context/CONVENTIONS.md` — Git section.

**Rule: One scope per commit. Never mix layers.**

### Commit Format

```
<type>(<scope>): <short description>
```

### Types

| Type | Use for |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | No behavior change |
| `test` | Tests only |
| `docs` | Docs only |
| `chore` | Tooling, config, deps |
| `perf` | Performance |
| `style` | Formatting/lint only |

### Scopes — use exactly one per commit

| Scope | What it covers |
|---|---|
| `backend` | FastAPI routes, services (general) |
| `schemas` | Pydantic v2 schemas only |
| `db` | SQLAlchemy ORM, Alembic migrations |
| `celery` | Celery tasks, queue config |
| `scoring` | PyTorch scorers, feature router |
| `litellm` | LiteLLM client, model config |
| `ws` | WebSocket handler |
| `mcp` | FastMCP server, MCP tools |
| `frontend` | Next.js pages, components, stores |
| `infra` | Docker, compose, gunicorn, Redis config |
| `tests` | Test files only |
| `docs` | Markdown in /docs/ or /context/ |
| `ci` | GitHub Actions, pre-commit, ruff |

### Examples

```bash
feat(schemas): add EvalConsumerConfig and FeatureFlag enum
feat(db): add alembic migration 001 with 5 core tables
feat(litellm): add LiteLLM wrapper with Langfuse callback
feat(celery): add run_eval_task with exponential backoff retry
feat(ws): add WebSocket eval streaming with Redis pub/sub
feat(scoring): add BERTScore F1 scorer with run_in_executor
feat(mcp): add run_eval and get_best_model MCP tools
feat(frontend): add eval runner page with live token streaming
feat(infra): add docker-compose with 8 services
fix(ws): add try/finally pubsub cleanup on disconnect
test(scoring): add BERTScore unit tests with deterministic input
docs(context): update CURRENT_STATE after Phase 2
chore(infra): add docker-compose.override for local dev
```

### What must NEVER be one commit

```
❌ feat(backend): add eval endpoint and update leaderboard page
   → two commits: feat(backend) + feat(frontend)

❌ feat(schemas): add schemas and write DB migration
   → two commits: feat(schemas) + feat(db)

❌ fix(ws): fix websocket, update tests, update docs
   → three commits: fix(ws) + test(ws) + docs(context)
```

### Branch naming

```
feature/phase-1a-infrastructure
feature/phase-2-eval-engine
fix/websocket-redis-cleanup
test/add-feature-router-coverage
docs/update-architecture
```

---

# 56. Golden Rule for AI Agents

Before making a change, understand:

```text
WHAT exists
WHY it exists
WHERE it belongs
WHAT depends on it
HOW it is tested
WHAT could break
```

After making a change, record:

```text
WHAT changed
WHY it changed
WHAT was tested
WHAT remains unresolved
```

---

# 56. Final Agent Instruction

When working on this project:

> **Do not treat the repository as merely source code. Treat it as a continuously evolving system with code, experiments, data, configuration, evaluation methodology, and historical decisions.**

Before implementing something new, understand the existing system.

Prefer small, testable, reversible changes.

Preserve provenance.

Preserve raw evaluation data.

Do not silently change evaluation methodology.

When you make an important decision, document why.

When an approach fails, document why it failed.

When the project's state changes, update the project context.

The objective is not merely to make the code work today.

The objective is to make the project understandable and maintainable by another engineer or AI agent months from now.

---

# 57. Quick Reference

```text
┌───────────────────────────────────────────────┐
│              AI AGENT WORKFLOW                │
├───────────────────────────────────────────────┤
│                                               │
│  1. Read project context                      │
│             ↓                                 │
│  2. Understand current state                  │
│             ↓                                 │
│  3. Inspect existing implementation           │
│             ↓                                 │
│  4. Identify correct architectural layer     │
│             ↓                                 │
│  5. Make smallest reasonable change           │
│             ↓                                 │
│  6. Run tests                                 │
│             ↓                                 │
│  7. Review diff                               │
│             ↓                                 │
│  8. Update context                            │
│             ↓                                 │
│  9. Record decisions/experiments              │
│             ↓                                 │
│ 10. Update current state                      │
│                                               │
└───────────────────────────────────────────────┘
```

```text
┌───────────────────────────────────────────────┐
│            EVALUATION DATA FLOW               │
├───────────────────────────────────────────────┤
│                                               │
│ Dataset + Prompt + Model + Evaluator          │
│                    ↓                          │
│              Experiment Run                   │
│                    ↓                          │
│              Model Execution                  │
│                    ↓                          │
│             Raw Model Output                  │
│                    ↓                          │
│               Evaluation                      │
│                    ↓                          │
│             Metric Results                    │
│                    ↓                          │
│             Aggregation                       │
│                    ↓                          │
│          Comparison / Reporting               │
│                                               │
└───────────────────────────────────────────────┘
```

**End of Project Guide**
