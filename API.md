# SmartOnboard API Reference

Base URL for local development:

```text
http://localhost:5000
```

## GET /api/health

Returns app health, cache count, LLM provider configuration status, and agent feature flag status.

Example:

```bash
curl http://localhost:5000/api/health
```

Response:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "cache_entries": 0,
  "agent_enabled": true,
  "llm": {
    "provider": "openrouter",
    "configured": true,
    "model": "meta-llama/llama-3.3-70b-instruct:free"
  }
}
```

---

## POST /api/analyze

Clones and deterministically analyzes a public GitHub repository, generates a role-specific onboarding guide, and caches the result for instant retrieval and agent reasoning.

Request:

```json
{
  "repo_url": "https://github.com/sindresorhus/is",
  "role": "engineer"
}
```

Roles:
- `engineer`
- `manager`
- `architect`

Response:

```json
{
  "status": "success",
  "cached": false,
  "data": {
    "repo_url": "https://github.com/sindresorhus/is",
    "repo_name": "is",
    "role": "engineer",
    "tech_stack": {
      "languages": ["TypeScript", "JavaScript"],
      "frameworks": [],
      "package_managers": ["npm"]
    },
    "structure": {
      "total_files": 19,
      "total_lines": 6552,
      "entry_points": ["source/index.ts"]
    },
    "key_files": [],
    "content": "# SmartOnboard Guide: is...",
    "analysis_time": "3s"
  }
}
```

---

## POST /api/chat

Answers questions using the cached repository analysis. When `AGENT_QA_ENABLED=true`, runs a multi-turn tool-calling ReAct agent over AST-aware hybrid RAG index and repository files.

Request:

```json
{
  "repo_url": "https://github.com/sindresorhus/is",
  "role": "engineer",
  "question": "Where is the type assertion logic implemented?",
  "history": []
}
```

Response:

```json
{
  "status": "success",
  "mode": "agent",
  "question": "Where is the type assertion logic implemented?",
  "answer": "The type assertion logic is located in `source/index.ts`...",
  "citations": ["source/index.ts"],
  "steps": 2,
  "usage": {
    "in": 1420,
    "out": 380
  }
}
```

---

## POST /api/chat/stream

Server-Sent Events (SSE) streaming endpoint for real-time agent execution traces and tokens.

Request:

```json
{
  "repo_url": "https://github.com/sindresorhus/is",
  "question": "How is authentication handled?",
  "history": []
}
```

Response stream (`text/event-stream`):

```text
data: {"type": "step", "n": 1, "tool": "search_code", "args": {"pattern": "auth"}}

data: {"type": "result", "n": 1, "summary": "Found 3 matches"}

data: {"type": "step", "n": 2, "tool": "read_file", "args": {"path": "source/auth.ts"}}

data: {"type": "done", "answer": "...", "citations": ["source/auth.ts"], "usage": {"in": 1200, "out": 250}}
```

---

## GET /api/runs

Returns the recent 20 agent execution traces and observability records.

Example:

```bash
curl http://localhost:5000/api/runs
```

Response:

```json
{
  "status": "success",
  "runs": [
    {
      "id": 1,
      "timestamp": "2026-10-10T01:30:00.000000",
      "repo_url": "https://github.com/sindresorhus/is",
      "question": "Where are type guards?",
      "mode": "agent",
      "steps": 2,
      "tools_used": ["search_code", "read_file"],
      "citations": ["source/index.ts"],
      "latency_ms": 1450,
      "tokens_in": 1240,
      "tokens_out": 310,
      "error": null
    }
  ]
}
```

---

## POST /api/export/{format}

Exports generated guide content in various formats.

Supported formats:
- `html`
- `markdown` / `md`
- `skill` (Claude Code / Agent Skill format)

Request:

```json
{
  "repo_url": "https://github.com/sindresorhus/is",
  "content": "# SmartOnboard Guide..."
}
```
