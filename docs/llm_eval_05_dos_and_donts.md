# LLM Eval Platform — Do's and Don'ts

## Architecture

### DO
- Keep the MCP server as a **separate process/service** from the FastAPI backend — they have different transport protocols (HTTP vs stdio/SSE)
- Use the **Feature Middleware Layer** as the single decision point for what runs — never scatter feature flags across the codebase
- Design every service to be **independently restartable** — the eval engine should work even if the frontend is down
- Store all configs as **Pydantic models** — never raw dicts or JSON strings in business logic
- Use **async everywhere** in the backend — never mix sync and async in the same call path

### DON'T
- Don't put scoring logic in API route handlers — it belongs in `services/scoring.py`
- Don't let consumer projects call LLMs directly — all LLM calls must go through this platform (that's the whole point)
- Don't build the frontend before the backend eval engine is tested — verify the engine works via pytest first
- Don't hardcode model names anywhere — always use the `ModelID` enum from schemas
- Don't share the same Redis instance for both Celery queue and WebSocket pub/sub without namespacing keys (`celery:*` vs `run:*`)

---

## Pydantic v2

### DO
```python
# Use model_validator for cross-field validation
class PromptRunRequest(BaseModel):
    prompt: str
    reference_output: str | None = None
    scoring_metrics: list[ScoringMetric]

    @model_validator(mode="after")
    def check_reference_required_for_bert(self) -> "PromptRunRequest":
        if ScoringMetric.BERT_SCORE in self.scoring_metrics:
            if self.reference_output is None:
                raise ValueError("reference_output required for BERTScore")
        return self


# Use Field with constraints
class EvalConsumerConfig(BaseModel):
    consumer_id: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9-]+$")
    models: list[ModelID] = Field(min_length=1, max_length=10)


# Use model_config for global settings
class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,  # for SQLAlchemy ORM → Pydantic conversion
        validate_assignment=True,  # validate on attribute set
        str_strip_whitespace=True,
    )
```

### DON'T
```python
# DON'T use dict() — it's deprecated in v2
data = my_model.dict()  # WRONG
data = my_model.model_dump()  # CORRECT

# DON'T use .parse_obj() — deprecated
model = MyModel.parse_obj(data)  # WRONG
model = MyModel.model_validate(data)  # CORRECT

# DON'T use Optional[X] — use X | None instead (Pydantic v2 style)
field: Optional[str] = None  # Old style
field: str | None = None  # Correct v2 style


# DON'T skip validation on config
class Config:  # Old v1 style
    orm_mode = True


# USE:
model_config = ConfigDict(from_attributes=True)  # v2 style
```

---

## Async Patterns

### DO
```python
# Use asyncio.gather for parallel model calls
async def run_all_models(prompt: str, models: list[str]) -> list[ModelResponse]:
    tasks = [call_single_model(prompt, model) for model in models]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]


# Use async context managers for DB sessions
async def get_eval_run(run_id: UUID) -> EvalRun | None:
    async with AsyncSession(engine) as session:
        return await session.get(EvalRunORM, run_id)


# Use FastAPI lifespan for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await init_db()
    await redis_client.ping()
    yield
    # shutdown
    await redis_client.aclose()
```

### DON'T
```python
# DON'T use sync LiteLLM calls in async context
response = litellm.completion(...)  # WRONG — blocks event loop
response = await litellm.acompletion(...)  # CORRECT

# DON'T create a new DB session per query
# Create a session factory and use dependency injection in FastAPI

# DON'T use time.sleep in async code
time.sleep(1)  # WRONG
await asyncio.sleep(1)  # CORRECT
```

---

## LiteLLM

### DO
```python
# Set up LiteLLM once at startup with all callbacks
import litellm

litellm.callbacks = [LangfuseHandler()]
litellm.set_verbose = False  # turn off in production

# Always pass metadata for Langfuse grouping
response = await litellm.acompletion(
    model=model_id,
    messages=messages,
    metadata={
        "run_id": str(run_id),
        "consumer_id": consumer_id,
        "task_type": task_type,
        "generation_name": f"eval-{model_id}",
    },
)

# Handle model-specific errors gracefully
try:
    response = await litellm.acompletion(...)
except litellm.RateLimitError:
    await asyncio.sleep(60)
    response = await litellm.acompletion(...)  # retry once
except litellm.AuthenticationError:
    raise ModelUnavailableError(model_id)
```

### DON'T
```python
# DON'T use different SDK per model — defeats LiteLLM's purpose
import google.generativeai as genai  # DON'T do this
from groq import Groq  # DON'T do this

# DON'T ignore the model prefix
litellm.completion(model="gemini-flash")  # WRONG — model not found
litellm.completion(model="gemini/gemini-3.5-flash")  # CORRECT
```

---

## PostgreSQL / SQLAlchemy

### DO
- Use **Alembic for every schema change** — never `Base.metadata.create_all()` in production
- Add **indexes** on columns you'll filter by: `consumer_id`, `task_type`, `created_at`, `model_id`
- Use **UUID primary keys** (not integer IDs) — safer for distributed systems
- Use **JSONB** for flexible config storage (consumer configs, rubrics)
- Use **connection pooling** via SQLAlchemy's `create_async_engine` with `pool_size`

### DON'T
- Don't use `session.execute(text("SELECT ..."))` for anything that has an ORM equivalent
- Don't forget `await session.commit()` after writes — async sessions don't auto-commit
- Don't store full prompt texts only in the `eval_runs` table — also store in `prompts` for deduplication
- Don't run migrations inside Docker on every startup — run them as a separate init step

---

## Redis

### DO
```python
# Namespace all keys
LEADERBOARD_CACHE_KEY = "cache:leaderboard:{task_type}"
RUN_CHANNEL_KEY = "run:{run_id}:{model_id}"
API_KEY_CACHE = "auth:apikey:{key_hash}"

# Always set TTL on cache keys
await redis.set(LEADERBOARD_CACHE_KEY, data, ex=300)  # 5 min TTL

# Use pub/sub with explicit channel subscription management
pubsub = redis.pubsub()
await pubsub.subscribe(f"run:{run_id}:*")
```

### DON'T
- Don't store large objects (full eval results) in Redis — that's PostgreSQL's job
- Don't use Redis as a primary database — cache and pub/sub only
- Don't forget to `await pubsub.unsubscribe()` when WebSocket disconnects (memory leak)
- Don't use `KEYS *` in production — use `SCAN` instead

---

## MCP Server

### DO
- Expose **focused, single-purpose tools** — `run_eval`, `get_best_model`, `get_eval_history` — not one giant "do everything" tool
- Return **Pydantic models** from MCP tools — FastMCP serializes them automatically
- Include **clear docstrings** on every MCP tool — they become the tool description in Cursor/Claude Desktop
- Test MCP tools with the `mcp` CLI before testing in Cursor: `mcp dev mcp/server.py`

### DON'T
- Don't make MCP tools do too much — keep them composable (agents chain them)
- Don't return raw dicts from MCP tools — always Pydantic models
- Don't put business logic in MCP tool handlers — they should call services, not implement logic
- Don't expose admin/destructive operations via MCP without auth

---

## WebSockets

### DO
- Handle **WebSocket disconnects gracefully** — use try/finally to clean up pub/sub subscriptions
- Send **structured JSON messages**, not plain text
- Include `run_id` and `model_id` in every streamed message so the frontend can route correctly
- Implement **ping/pong keepalive** for long-running eval streams

### DON'T
```python
# DON'T put eval logic inside the WebSocket handler
@app.websocket("/ws/eval/{run_id}")
async def ws_handler(ws: WebSocket, run_id: UUID):
    # DON'T run evals here — just subscribe to Redis and forward
    # Eval runs via Celery, WebSocket only forwards from Redis pub/sub
```

---

## PyTorch / Scoring

### DO
- Load PyTorch models **once at startup** — never load them per request (slow)
- Use **GPU if available**, fall back to CPU: `device = "cuda" if torch.cuda.is_available() else "cpu"`
- Wrap PyTorch calls in `asyncio.run_in_executor` to avoid blocking the event loop:
```python
loop = asyncio.get_event_loop()
score = await loop.run_in_executor(None, compute_bert_score, candidate, reference)
```
- Cache scoring model instances in a module-level singleton

### DON'T
- Don't run BERTScore synchronously in a FastAPI route handler — it blocks for seconds
- Don't download models at runtime — pre-download in Dockerfile or startup script
- Don't use GPU for scoring in a Docker container unless you configure GPU passthrough

---

## Testing

### DO
- **Mock LiteLLM** in unit tests — never make real API calls in tests
- Test the **Feature Middleware** separately — it's the most critical routing logic
- Use **pytest fixtures** for DB session + Redis + async client
- Test **WebSocket streaming** with `httpx` async client's WebSocket support
- Aim for tests on: eval runner, scoring, MCP tools, feature router, API endpoints

### DON'T
- Don't test only happy paths — test: model timeout, rate limit, malformed response, WebSocket disconnect
- Don't use `pytest.mark.asyncio` on every test individually — configure globally in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```
