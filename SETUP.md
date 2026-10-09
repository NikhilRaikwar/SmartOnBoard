# SmartOnboard Setup & Local Development

## Prerequisites

- Python 3.9+
- Git available on `PATH`
- Public internet access for GitHub repository cloning
- Optional OpenRouter or AIML API key (or `LLM_PROVIDER=mock` for zero-key local testing)

---

## 1. Installation

```bash
# Clone and enter workspace
cd SmartOnboard

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

---

## 2. Configuration (`.env`)

```env
# Provider options: openrouter | aiml | mock
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

# Fallback provider
AIML_API_KEY=your_aiml_api_key_here
AIML_MODEL=meta-llama/Llama-3.3-70B-Instruct-Turbo

# ReAct Agent switch
AGENT_QA_ENABLED=false

# App Settings
FLASK_DEBUG=True
SECRET_KEY=dev-secret-key-change-in-production
MAX_REPO_SIZE_MB=500
MAX_ANALYZED_FILES=500
```

> [!NOTE]
> **Keyless Development:** If no API keys are configured, SmartOnboard automatically uses deterministic factual analysis. You can also set `LLM_PROVIDER=mock` to test full ReAct agent loops and hybrid RAG search completely offline.

---

## 3. Running Locally

```bash
python app.py
```

Access the app in your browser:
```text
http://localhost:5000
```

---

## 4. Verifying Installation

### Health Check
```bash
curl http://localhost:5000/api/health
```

### Analyze a Repo
```bash
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/sindresorhus/is","role":"engineer"}'
```

### Run Keyless Test Suite
```bash
python -m pytest tests/ -v
```

---

## 5. Troubleshooting

- **Git is not available:** Install Git or ensure `git` is added to your system `PATH`. On serverless runtimes without git, SmartOnboard automatically falls back to GitHub archive ZIP downloads.
- **Port 5000 in use:** Set `PORT=5001` in your environment or command line: `PORT=5001 python app.py`.
