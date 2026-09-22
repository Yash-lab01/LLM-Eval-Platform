# Architecture Decisions

## ADR-001 — LiteLLM as Sole Provider Gateway
Date: 2026-09-22 | Status: Accepted

**Decision:** Use LiteLLM as the only way to call LLMs. No Gemini SDK, no Groq SDK, no Ollama SDK directly.

**Reason:** Single import, single retry config, single observability hook. Adding a new model = adding one enum value.

**Tradeoff:** Slight abstraction overhead. Worth it for model-agnostic architecture.

---

## ADR-002 — Feature Middleware Layer
Date: 2026-09-22 | Status: Accepted

**Decision:** All feature gating goes through `FeatureRouter` in `backend/middleware/feature_router.py`. Consumer projects declare what they need via `EvalConsumerConfig`. The router decides what runs.

**Reason:** Prevents feature flags from being scattered across 10 files. Makes the platform a true "plug-in" tool for consumer projects.

**Tradeoff:** More upfront design. But makes the platform reusable across all future projects.

---

## ADR-003 — Redis DB Separation (3 DBs)
Date: 2026-09-22 | Status: Accepted

**Decision:** Redis DB 0 = general cache + pub/sub. DB 1 = Celery broker. DB 2 = Celery result backend.

**Reason:** Celery keys (uuid-based) pollute cache namespace. Pub/sub channels for WebSocket need clean isolation.

**Tradeoff:** Slightly more config. Prevents hard-to-debug key collisions.

---

## ADR-004 — MCP Dual Transport (stdio + Streamable HTTP)
Date: 2026-09-22 | Status: Accepted

**Decision:** MCP server supports both stdio (for Cursor/Claude Desktop) and streamable-http (for server deployment).

**Reason:** stdio is zero-config for local IDE integration. HTTP is required for remote/multi-user deployment.

**Tradeoff:** Two entry points to maintain. Both needed for full portfolio demo.

---

## ADR-005 — PyTorch Models Loaded at Startup
Date: 2026-09-22 | Status: Accepted

**Decision:** BERTScore model and sentence transformer loaded once in FastAPI lifespan startup event, stored as module-level singletons.

**Reason:** Loading per-request takes 2–5 seconds. Unacceptable for a scoring API.

**Tradeoff:** Higher memory usage at startup. Acceptable for this use case.

---

## ADR-006 — Pydantic v2 as Single Schema Layer
Date: 2026-09-22 | Status: Accepted

**Decision:** Every data contract (API request/response, MCP tool I/O, Celery payloads, scoring results) is a Pydantic v2 model in `backend/schemas/`. No ad-hoc dicts in business logic.

**Reason:** Auto-generates OpenAPI docs. Auto-generates MCP tool schemas. Type safety at every boundary.

**Tradeoff:** More upfront schema work. Pays off immediately in Phase 2+.

---

## ADR-007 — No OpenAI or Anthropic API
Date: 2026-09-22 | Status: Accepted

**Decision:** Only free-tier models: Gemini (Google), Groq (Llama/Qwen/Mixtral), Ollama (local).

**Reason:** No paid API keys available.

**Tradeoff:** Limited to free-tier rate limits. Mitigated by Celery retry with exponential backoff.
