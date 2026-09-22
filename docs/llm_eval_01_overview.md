# LLM Eval Platform — Project Overview

## What Is This?

A **modular, self-hosted LLM evaluation and benchmarking platform** that:
1. Runs any prompt across multiple LLMs simultaneously and scores the results
2. Logs every LLM interaction with full observability (traces, latency, cost)
3. Exposes an **MCP server** so any other project can plug into it as a tool
4. Uses a **middleware config layer** so each consumer project only activates the features it needs

Think: a self-hosted mini-LangSmith + LLM Leaderboard + MCP Tool Hub — all in one.

---

## The Core Problem It Solves

When building LLM-powered apps, developers face three recurring questions:
- **Which model** is best for my specific task type?
- **Is my prompt degrading** over time as models update?
- **How do I observe** what my LLM is doing in production?

This platform answers all three — and because it's exposed as an **MCP server**, it can answer them *from inside any agent or IDE* without switching tabs.

---

## Ecosystem Role

```
┌─────────────────────────────────────────────────────────┐
│                   Your Future Projects                   │
│                                                          │
│  AI Terminal Agent  ←──┐                                │
│  AI Research Agent  ←──┤   MCP / REST API calls        │
│  AI Travel Agent    ←──┤   (only features they need)   │
│  Any Future Agent   ←──┘                                │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│            LLM Eval Platform  (this project)            │
│                                                          │
│  ┌─────────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │  Eval Engine│  │  Observability│  │  MCP Server  │  │
│  │  (LiteLLM + │  │  (Langfuse /  │  │  (tools for  │  │
│  │   PyTorch)  │  │   Phoenix)    │  │   agents)    │  │
│  └─────────────┘  └───────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │   Feature Middleware Layer (the smart router)    │   │
│  │   Reads consumer config → activates only what's  │   │
│  │   needed per project                             │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  PostgreSQL · Redis · LiteLLM · Pydantic v2             │
└─────────────────────────────────────────────────────────┘
```

---

## Key Differentiators

| What | Why it matters |
|---|---|
| **Modular feature middleware** | Each consumer project activates only what it needs — no bloat |
| **MCP-first design** | Works inside Cursor, Claude Desktop, any MCP-compatible IDE |
| **PyTorch eval metrics** | Real semantic scoring (BERTScore), not just LLM-as-judge |
| **Self-hostable** | No paid APIs required — Gemini free tier + Groq free + Ollama local |
| **Portfolio multiplier** | Every future project plugs into this — your GitHub tells a connected story |

---

## What This Is NOT

- Not a model training platform (no training loops here)
- Not a prompt engineering UI (prompts are inputs, not the product)
- Not a replacement for Langfuse (it *uses* Langfuse as one layer)
- Not a model hosting service (uses APIs and local Ollama)
