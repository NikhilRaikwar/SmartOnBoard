# SmartOnboard Setup

## Prerequisites

- Python 3.9+
- Git available on `PATH`
- Public internet access for GitHub clone
- Optional IBM watsonx.ai credentials

## Install

```bash
cd smartonboard
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

```env
WATSONX_API_KEY=your_key
WATSONX_PROJECT_ID=your_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=meta-llama/llama-3-3-70b-instruct
SECRET_KEY=replace_me
MAX_ANALYZED_FILES=500
```

watsonx is optional. If credentials are missing, the app still produces deterministic onboarding guides from real repository scans.

## Run

```bash
python app.py
```

Open:

```text
http://localhost:5000
```

## Verify

Health:

```bash
curl http://localhost:5000/api/health
```

Analyze:

```bash
curl -X POST http://localhost:5000/api/analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"repo_url\":\"https://github.com/sindresorhus/is\",\"role\":\"engineer\",\"use_watsonx\":true}"
```

## Troubleshooting

### `Git is not installed or is not available on PATH`

Install Git and verify:

```bash
git --version
```

### watsonx is configured but not available

Check `/api/health`. The app uses the SDK if installed and otherwise uses watsonx REST through `requests`.

Common causes:

- Invalid API key
- Wrong project ID
- Model unavailable in your region/project
- Network timeout

The app falls back to the deterministic guide if watsonx generation fails.

### Port 5000 already in use

Set a different port:

```bash
set PORT=5001
python app.py
```

### Python command not found on Windows

Use the Python launcher:

```bash
py -3 app.py
```
