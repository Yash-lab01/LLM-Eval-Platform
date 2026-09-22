# LLM Eval Platform — Features Specification

## Feature Middleware Layer (The Architectural Key)

Before listing features, understand how they are consumed:

Every project that plugs into this platform sends a **consumer config** (Pydantic model) declaring what it needs:

```python
# Example: AI Terminal Agent connecting to eval platform
class EvalConsumerConfig(BaseModel):
    consumer_id: str                        # "ai-terminal-agent"
    features: list[FeatureFlag]             # what to activate
    models: list[str]                       # which LLMs to use
    task_type: TaskType                     # what kind of task
    scoring_metrics: list[ScoringMetric]    # which metrics to compute

# Terminal Agent only needs basic scoring + observability
config = EvalConsumerConfig(
    consumer_id="ai-terminal-agent",
    features=[FeatureFlag.BASIC_SCORING, FeatureFlag.OBSERVABILITY],
    models=["gemini-flash", "groq-llama"],
    task_type=TaskType.CODE_GENERATION,
    scoring_metrics=[ScoringMetric.BERT_SCORE, ScoringMetric.LATENCY]
)
```

The middleware reads this config and only spins up the required pipeline components. No RAG eval, no hallucination check, no batch eval — unless the consumer asks.

---

## Core Features (MVP — Phase 1 & 2)

### CF-01: Multi-Model Prompt Runner
**What**: Send the same prompt to multiple LLMs at the same time and collect responses in parallel.

**How**:
- LiteLLM as the unified gateway — one API call format for Gemini, Groq, Ollama
- asyncio + async generators for true parallel execution
- Results collected via asyncio.gather()

**Models supported (all free)**:
- `gemini/gemini-3.5-flash` (Google free tier)
- `gemini/gemini-3.8-flash` (Google free tier)
- `groq/openai/gpt-oss-120b` (Groq free tier)
- `groq/openai/gpt-oss-20b` (Groq free tier)
- `groq/qwen/qwen3.8-27b` (Groq free tier)
- `groq/qwen/qwen3-32b` (Groq free tier)
- `ollama/llama3.2` (local, no API)
- `ollama/mistral` (local, no API)

**Pydantic schemas**:
```python
class PromptRunRequest(BaseModel):
    prompt: str
    task_type: TaskType
    models: list[ModelID]
    consumer_config: EvalConsumerConfig
    reference_output: str | None = None     # for scoring

class ModelResponse(BaseModel):
    model_id: ModelID
    output: str
    latency_ms: float
    token_count: int
    finish_reason: str
    timestamp: datetime
```

---

### CF-02: Real-Time Streaming via WebSockets
**What**: Model responses stream live to the frontend — you see tokens appearing in real time, side by side per model.

**How**:
- FastAPI WebSocket endpoint `/ws/eval/{run_id}`
- LiteLLM streaming mode → async generator → WebSocket push
- Frontend subscribes to run_id channel
- Redis pub/sub used as message broker between eval workers and WebSocket server

**Message format** (streamed per token):
```json
{
  "run_id": "uuid",
  "model_id": "groq/llama-3.3",
  "token": "The",
  "is_final": false,
  "metadata": {}
}
```

---

### CF-03: Automated Scoring Engine
**What**: After all models respond, compute multiple objective scores automatically.

**Scoring metrics**:

| Metric | What | Tech |
|---|---|---|
| **BERTScore** | Semantic similarity to reference output | PyTorch + `bert-score` library |
| **ROUGE-L** | N-gram overlap with reference | `rouge-score` library |
| **Latency** | Time to first token + full response time | asyncio timing |
| **Token Count** | Input + output tokens | LiteLLM response metadata |
| **Estimated Cost** | Based on token count + model pricing | LiteLLM cost calculation |

**Why BERTScore with PyTorch**:
- Uses BERT's contextual embeddings — understands semantics, not just word overlap
- PyTorch runs the model locally — no API calls, no cost
- Far more meaningful than ROUGE for most NLP tasks

**Pydantic schemas**:
```python
class EvalScore(BaseModel):
    model_id: ModelID
    bert_score_f1: float | None
    rouge_l: float | None
    latency_ms: float
    token_count: int
    estimated_cost_usd: float

class EvalRunResult(BaseModel):
    run_id: UUID
    prompt: str
    task_type: TaskType
    scores: list[EvalScore]
    winner: ModelID | None
    created_at: datetime
```

---

### CF-04: Prompt Library
**What**: Save, version, tag, and organize prompts. Never rewrite the same prompt twice.

**How**:
- PostgreSQL table: `prompts` with version history
- Prompt templates with variable interpolation (Jinja2-style)
- Tag by task type, model, project

**Features**:
- Version history — roll back to previous prompt version
- "Clone & Edit" workflow
- Template variables: `"Summarize the following: {{text}}"`

---

### CF-05: Task Type Classification System
**What**: Every eval run is tagged with a task type. Scores are tracked per task type, building model-vs-task intelligence over time.

**Task types** (Pydantic Enum):
```python
class TaskType(str, Enum):
    SUMMARIZATION = "summarization"
    QUESTION_ANSWERING = "question_answering"
    CODE_GENERATION = "code_generation"
    DATA_EXTRACTION = "data_extraction"
    CREATIVE_WRITING = "creative_writing"
    CLASSIFICATION = "classification"
    TRANSLATION = "translation"
    RAG_RESPONSE = "rag_response"          # for RAG eval mode
    COMMAND_GENERATION = "command_generation"  # for terminal agent
```

---

### CF-06: Model Leaderboard
**What**: Aggregated win-rate per model per task type, built from all historical eval runs.

**How**:
- PostgreSQL aggregation queries over `eval_runs` table
- Cached in Redis (TTL: 5 minutes) — leaderboard doesn't need to be real-time
- Displayed as a ranked table + radar chart per task type

**Data shown**:
- Win rate (%) per task type
- Average BERTScore per task type
- Average latency
- Total evals run
- Trend (improving / degrading over last 7 days)

---

### CF-07: Eval History & Search
**What**: Every single eval run is stored — fully searchable and filterable.

**Storage**: PostgreSQL with indexes on `task_type`, `model_id`, `created_at`, `consumer_id`

**Query capabilities**:
- Filter by model, task type, date range, score range, consumer project
- Compare two specific runs side by side
- Export any filtered set

---

### CF-08: LLM Observability (Langfuse Integration)
**What**: Every LLM call is automatically traced — prompt, response, latency, cost, model, token count — without any extra code in consumer projects.

**How**:
- Langfuse SDK hooked into LiteLLM callbacks
- One line setup: `litellm.callbacks = [LangfuseHandler()]`
- Every call auto-logged → Langfuse dashboard
- Consumer projects get observability **for free** just by routing through this platform

**What Langfuse shows**:
- Full trace tree per eval run
- Token cost breakdown per model
- P50/P95 latency per model
- Error rate per model
- Session-level grouping by consumer project

---

### CF-09: MCP Server
**What**: The entire eval platform exposed as MCP tools — usable inside Cursor, Claude Desktop, or any MCP-compatible environment.

**MCP Tools exposed**:

```python
@mcp_server.tool()
async def run_eval(
    prompt: str,
    task_type: str,
    models: list[str],
    consumer_id: str,
    features: list[str]
) -> EvalRunResult:
    """Run a prompt across specified LLMs and return scored results."""

@mcp_server.tool()
async def get_best_model(
    task_type: str,
    metric: str = "bert_score"
) -> ModelRecommendation:
    """Get the best-performing model for a given task type based on history."""

@mcp_server.tool()
async def get_eval_history(
    consumer_id: str,
    limit: int = 20
) -> list[EvalRunSummary]:
    """Get recent eval history for a specific consumer project."""

@mcp_server.tool()
async def compare_runs(
    run_id_a: str,
    run_id_b: str
) -> RunComparison:
    """Compare two eval runs side by side."""
```

**MCP Config for consumer projects**:
```json
{
  "mcpServers": {
    "llm-eval": {
      "url": "http://localhost:8001/mcp",
      "description": "LLM evaluation and benchmarking platform"
    }
  }
}
```

---

### CF-10: Pydantic v2 Throughout
**What**: Every single data contract in the system — API requests, DB models, MCP inputs/outputs, scoring results, configs — defined as Pydantic v2 models.

**Why this matters**:
- Catches bad data at the boundary, not deep inside business logic
- Auto-generates OpenAPI docs for all endpoints
- Enables strict type checking across the whole codebase
- MCP tool schemas auto-generated from Pydantic models

**Key model families**:
- `EvalConsumerConfig` — what a consumer project declares it needs
- `PromptRunRequest / PromptRunResult` — eval input/output
- `ModelResponse / EvalScore / EvalRunResult` — scoring results
- `LeaderboardEntry` — aggregated model performance
- `ObservabilityConfig` — Langfuse/Phoenix settings per consumer

---

## Extra Features (Post-MVP — Phase 3+)

### EF-01: Batch Eval
**What**: Upload a CSV or JSON file of prompts + reference outputs → run all of them through the eval engine automatically.

**Use case**: Regression testing — run your 50-prompt test set every time you switch models.

**How**:
- File upload endpoint → parse with Pandas + validate each row with Pydantic
- Redis Queue (RQ) or Celery for background batch processing
- Progress streamed via WebSockets (X of N complete)
- Results downloadable as CSV when done

---

### EF-02: LLM-as-Judge (G-Eval Style)
**What**: Use a capable LLM (Gemini 2.5 Flash) to score another model's output using a structured rubric.

**When to use**: Tasks where there's no single "correct" reference output (creative writing, open-ended QA).

**How**:
- Define a rubric (JSON) with criteria + weights
- Gemini receives: prompt + model output + rubric → returns JSON scores
- Scores validated with Pydantic, stored alongside automated scores

**Feature flag**: `FeatureFlag.LLM_AS_JUDGE` — not activated unless consumer requests it.

---

### EF-03: Custom Rubric Scoring
**What**: Define your own scoring criteria per task type. Goes beyond generic BERTScore.

**Example rubric for code generation**:
```json
{
  "criteria": [
    {"name": "correctness", "weight": 0.5, "description": "Does the code run?"},
    {"name": "readability", "weight": 0.3, "description": "Is it readable?"},
    {"name": "efficiency", "weight": 0.2, "description": "Is it efficient?"}
  ]
}
```

---

### EF-04: Regression Testing Mode
**What**: Save a "prompt suite" (collection of prompts + expected outputs) and re-run it on demand or on schedule.

**Use case**: You switch from Groq Llama to Groq Qwen. Run your saved suite → see exactly where performance improved or degraded.

**Output**: A regression report showing score delta per prompt per metric.

---

### EF-05: RAG Eval Mode
**What**: Specialized eval pipeline for RAG systems — measures retrieval quality separately from generation quality.

**Metrics**:
- **Context Relevance**: Is the retrieved context relevant to the question?
- **Faithfulness**: Does the answer stay within the retrieved context?
- **Answer Relevance**: Does the answer actually answer the question?

**How**: Uses PyTorch NLI model for faithfulness + BERTScore for relevance.

**Feature flag**: `FeatureFlag.RAG_EVAL` — only activated for RAG consumer projects.

---

### EF-06: Hallucination Score
**What**: Detect factual inconsistency between model output and a provided reference document using NLI (Natural Language Inference).

**How**:
- PyTorch NLI model (e.g., `cross-encoder/nli-deberta-v3-base` from HuggingFace)
- Sentence-level: each sentence in output → entailment/neutral/contradiction w.r.t. reference
- Aggregated into a single hallucination risk score (0–1)

---

### EF-07: Embedding Visualizer
**What**: 2D scatter plot showing how semantically similar/different each model's output is from each other and from the reference.

**How**:
- Embed all outputs with a sentence transformer (PyTorch)
- Reduce to 2D with UMAP
- Plot in frontend with D3.js or Plotly

**Use**: Visually see if models are "agreeing" or diverging on a prompt.

---

### EF-08: Export Reports
**What**: Download any eval run, batch result, or leaderboard view as:
- CSV (raw data)
- JSON (structured)
- PDF (formatted report with charts)

**PDF generation**: `weasyprint` or `reportlab` from Python.

---

### EF-09: Webhook Notifications
**What**: Define score thresholds per consumer project → get notified (HTTP webhook or email) when a model drops below them.

**Example**: "Alert me when BERTScore for code_generation drops below 0.75 for any model."

**How**:
- Redis-based threshold checker runs after every eval
- Celery task sends the webhook if threshold breached

---

### EF-10: Public REST API
**What**: Full REST API so external apps can trigger evals, query history, and get model recommendations without MCP.

**Key endpoints**:
```
POST   /api/v1/eval/run          — trigger an eval run
GET    /api/v1/eval/{run_id}     — get run results
GET    /api/v1/leaderboard       — get model leaderboard
GET    /api/v1/models/recommend  — best model for task type
POST   /api/v1/batch/upload      — upload batch eval file
GET    /api/v1/history           — query eval history
```

**Auth**: API key per consumer project (stored in PostgreSQL, cached in Redis).
