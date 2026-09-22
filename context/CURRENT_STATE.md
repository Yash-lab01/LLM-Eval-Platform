# Current State

Last updated: 2026-09-22
Current phase: Phase 0 — Pre-Build Setup (NOT STARTED)

## Current Focus
Project planning and documentation complete. Ready to begin Phase 0.

## Completed
- [x] All 5 docs written in /docs/
- [x] PROJECT_GUIDE.md updated with project-specific details
- [x] Phases reviewed and expanded to 10 phases
- [x] context/ folder created

## In Progress
- Nothing yet — code has not been written

## Phase Status
| Phase | Status |
|---|---|
| Phase 0: Pre-Build Setup | Not started |
| Phase 1A: Infrastructure | Not started |
| Phase 1B: Data Layer + Schemas | Not started |
| Phase 2: Core Eval Engine | Not started |
| Phase 3: Scoring + Feature Router | Not started |
| Phase 4: Observability + MCP | Not started |
| Phase 5: Frontend | Not started |
| Phase 6: Testing + Hardening | Not started |
| Phase 7A: Extra Features Core | Not started |
| Phase 7B: Extra Features Advanced | Not started |
| Phase 8: Portfolio Polish | Not started |

## Known Problems
None yet — project not started.

## Next Task
Phase 0: Install Python 3.12, Poetry, Docker Desktop, Node.js 20.
Get Gemini free API key and Groq free API key.

## Do Not Change
- ModelID enum values (LiteLLM prefix format must match exactly)
- Redis DB allocation: DB 0 = cache, DB 1 = Celery broker, DB 2 = Celery results
- Feature Middleware location: always backend/middleware/feature_router.py
- All Pydantic schemas live only in backend/schemas/ — nowhere else
