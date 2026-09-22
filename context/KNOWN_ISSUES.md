# Known Issues

## Format

```
## ISSUE-{ID} — {Title}
Status: Open | Resolved
Severity: High | Medium | Low
Phase: {phase where this matters}

Description:
What the issue is.

Impact:
What breaks or degrades.

Workaround:
What to do until fixed.

Planned Solution:
How to fix it properly.
```

---

## No Issues Yet

Project has not started. Issues will be logged here as they are discovered during development.

---

## Pre-Known Risks (not issues yet, but watch for these)

### Risk-01 — Groq Rate Limits
**Phase**: 2, 3
Groq free tier has strict RPM limits. Parallel model runs may hit limits quickly.
**Mitigation**: Celery retry with exponential backoff (already planned). Use `eval_default` queue to control concurrency.

### Risk-02 — PyTorch Startup Time
**Phase**: 3
Loading BERTScore model at startup may add 5–10 seconds to cold start.
**Mitigation**: Load in lifespan event, not per-request. Document expected startup time in README.

### Risk-03 — Langfuse Self-Hosted Memory
**Phase**: 1A
Langfuse v3 uses ClickHouse internally which is memory-hungry.
**Mitigation**: Allocate at least 4GB RAM to Docker. If too heavy, use Langfuse cloud free tier instead.

### Risk-04 — WebSocket Memory Leak
**Phase**: 2
If `pubsub.unsubscribe()` is not called on disconnect, Redis subscriptions accumulate.
**Mitigation**: Always use try/finally in WebSocket handler. Already documented in Phase 2 patterns.
