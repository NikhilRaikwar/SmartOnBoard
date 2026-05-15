# SmartOnboard API

Base URL for local development:

```text
http://localhost:5000
```

## GET /api/health

Returns app status, cache count, and watsonx configuration status.

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
  "watsonx": {
    "configured": true,
    "available": true,
    "model_id": "meta-llama/llama-3-3-70b-instruct",
    "error": null
  }
}
```

## POST /api/analyze

Clones and analyzes a public GitHub repository, generates a role-specific onboarding guide, and caches the result.

Request:

```json
{
  "repo_url": "https://github.com/sindresorhus/is",
  "role": "engineer",
  "use_watsonx": true
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
    "tech_stack": {},
    "structure": {},
    "key_files": [],
    "content": "# SmartOnboard Guide...",
    "analysis_time": "4s",
    "watsonx": {}
  }
}
```

## POST /api/chat

Answers questions using the cached repository analysis. Analyze the repository first.

Request:

```json
{
  "repo_url": "https://github.com/sindresorhus/is",
  "role": "engineer",
  "question": "What should I read first?"
}
```

Response:

```json
{
  "status": "success",
  "question": "What should I read first?",
  "answer": "Start with these files...",
  "watsonx": {}
}
```

## POST /api/export/{format}

Exports generated guide content.

Formats:

- `html`
- `markdown`
- `md`
- `skill`

Request:

```json
{
  "repo_url": "https://github.com/sindresorhus/is",
  "content": "# SmartOnboard Guide..."
}
```

The response is a downloadable file.

