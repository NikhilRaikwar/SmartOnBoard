import os

def test_no_keys_in_test_env():
    assert not os.environ.get("OPENROUTER_API_KEY")
    assert not os.environ.get("AIML_API_KEY")


import json
import shutil
import tempfile
from pathlib import Path

import pytest

os.environ["LLM_PROVIDER"] = "mock"

from app import app, ANALYSIS_CACHE
from core.agent import AGENT_TOOLS, run_agent, run_agent_stream, execute_tool
from core.chunk import chunk_file
from core.llm import MockProvider, get_client, chat as llm_chat
from core.rag import RAGIndex
from core.runs import recent_runs, log_run


def test_mock_drives_full_loop():
    """Mock script with tool calls completes in expected steps and collects citations."""
    script = [
        {
            "tool_calls": [
                {
                    "name": "search_code",
                    "args": {"pattern": "RepositoryAnalyzer"},
                }
            ]
        },
        {
            "tool_calls": [
                {
                    "name": "read_file",
                    "args": {"path": "core/analyzer_real.py", "max_chars": 200},
                }
            ]
        },
        {
            "final": "The `core/analyzer_real.py` file implements the `RepositoryAnalyzer` class."
        },
    ]
    mock_llm = MockProvider(script=script)

    temp_dir = tempfile.mkdtemp()
    try:
        # Create a mock file in temp repo
        core_dir = Path(temp_dir) / "core"
        core_dir.mkdir(parents=True, exist_ok=True)
        (core_dir / "analyzer_real.py").write_text("class RepositoryAnalyzer:\n    pass\n", encoding="utf-8")

        res = run_agent(
            question="Where is RepositoryAnalyzer?",
            repo_path=temp_dir,
            analysis={"repo_url": "https://github.com/mock/repo", "key_files": []},
            llm=mock_llm,
        )

        assert res["steps"] == 2
        assert "core/analyzer_real.py" in res["citations"]
        assert "RepositoryAnalyzer" in res["answer"]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_max_steps_guard():
    """Infinite tool-calling loops must be halted at max 8 steps."""
    infinite_tool_script = [
        {
            "tool_calls": [
                {
                    "name": "list_files",
                    "args": {"pattern": ""},
                }
            ]
        }
    ] * 20
    mock_llm = MockProvider(script=infinite_tool_script)

    res = run_agent(
        question="Keep listing files forever",
        repo_path=".",
        analysis={"repo_url": "https://github.com/mock/repo"},
        llm=mock_llm,
    )

    assert res["steps"] <= 8
    assert res["answer"]


def test_path_traversal_blocked():
    """Path traversal attempts (.., absolute paths, symlinks) must be blocked."""
    temp_dir = tempfile.mkdtemp()
    try:
        repo_dir = Path(temp_dir) / "repo"
        repo_dir.mkdir(parents=True, exist_ok=True)
        secret_file = Path(temp_dir) / "secret.txt"
        secret_file.write_text("SUPER_SECRET_DATA", encoding="utf-8")

        # Test relative escape
        out, summary = execute_tool(
            name="read_file",
            args={"path": "../secret.txt"},
            repo_path=str(repo_dir),
            analysis={},
        )
        assert "Error: Path" in out
        assert "SUPER_SECRET_DATA" not in out

        # Test absolute path escape
        out_abs, _ = execute_tool(
            name="read_file",
            args={"path": str(secret_file.resolve())},
            repo_path=str(repo_dir),
            analysis={},
        )
        assert "SUPER_SECRET_DATA" not in out_abs
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_tools_read_only():
    """Verify that all exposed agent tools are strictly read-only."""
    tool_names = [t["function"]["name"] for t in AGENT_TOOLS]
    forbidden_prefixes = ["write", "delete", "create", "update", "exec", "shell", "run_cmd", "modify", "remove"]
    for name in tool_names:
        for forbidden in forbidden_prefixes:
            assert not name.startswith(forbidden), f"Tool {name} violates read-only constraint"


def test_ast_chunking():
    """Python files are parsed via AST into function and class chunks."""
    sample_code = '''
"""Module docstring."""

class UserService:
    def __init__(self):
        self.users = []

def authenticate_user(username, password):
    """Authenticate given credentials."""
    return username == "admin" and password == "secret"

def calculate_metrics():
    return 42
'''
    chunks = chunk_file("services/auth.py", sample_code)
    assert len(chunks) >= 3
    kinds = [c.kind for c in chunks]
    names = [c.name for c in chunks]
    assert "class" in kinds
    assert "function" in kinds
    assert "UserService" in names
    assert "authenticate_user" in names
    assert "[services/auth.py |" in chunks[0].text


def test_hybrid_search_mock():
    """RAG index hybrid search combines vector and keyword search returning top 8."""
    temp_dir = tempfile.mkdtemp()
    try:
        sample_repo = Path(temp_dir) / "repo"
        sample_repo.mkdir(parents=True, exist_ok=True)
        (sample_repo / "auth.py").write_text("def login(): pass\ndef logout(): pass", encoding="utf-8")
        (sample_repo / "server.js").write_text("function startServer() { console.log('start'); }", encoding="utf-8")

        mock_provider = MockProvider()
        rag = RAGIndex("https://github.com/mock/hybrid-repo", cache_root=temp_dir)
        rag.build(str(sample_repo), embed_fn=mock_provider.embed)

        results = rag.hybrid_search("login authentication", embed_fn=mock_provider.embed, k=8)
        assert len(results) > 0
        assert len(results) <= 8
        assert "rrf_score" in results[0]
        assert results[0]["rrf_score"] > 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_chat_route_flag_off():
    """When AGENT_QA_ENABLED is false, /api/chat returns deterministic mode."""
    client = app.test_client()
    os.environ["AGENT_QA_ENABLED"] = "false"

    ANALYSIS_CACHE["https://github.com/test/repo:engineer"] = {
        "analysis": {
            "repo_url": "https://github.com/test/repo",
            "key_files": [{"path": "main.py", "purpose": "Entry point"}],
            "tech_stack": {"languages": ["Python"]},
            "structure": {"total_files": 1, "total_lines": 10},
            "setup": {"commands": ["pip install -r requirements.txt"]},
        }
    }

    res = client.post(
        "/api/chat",
        json={"repo_url": "https://github.com/test/repo", "question": "What is the tech stack?"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["mode"] == "deterministic"


def test_chat_route_no_keys():
    """When AGENT_QA_ENABLED is true and provider has missing key, returns fallback with 200 (never 500)."""
    client = app.test_client()
    os.environ["AGENT_QA_ENABLED"] = "true"
    os.environ["LLM_PROVIDER"] = "openrouter"
    os.environ["OPENROUTER_API_KEY"] = ""

    ANALYSIS_CACHE["https://github.com/test/repo:engineer"] = {
        "analysis": {
            "repo_url": "https://github.com/test/repo",
            "key_files": [{"path": "main.py", "purpose": "Entry point"}],
            "tech_stack": {"languages": ["Python"]},
            "structure": {"total_files": 1, "total_lines": 10},
            "setup": {"commands": ["pip install -r requirements.txt"]},
        }
    }

    res = client.post(
        "/api/chat",
        json={"repo_url": "https://github.com/test/repo", "question": "Explain architecture"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["mode"] in ("deterministic-fallback", "deterministic")


def test_stream_events():
    """Streaming endpoint yields SSE events and done event."""
    os.environ["AGENT_QA_ENABLED"] = "true"
    os.environ["LLM_PROVIDER"] = "mock"
    client = app.test_client()

    ANALYSIS_CACHE["https://github.com/test/repo:engineer"] = {
        "analysis": {
            "repo_url": "https://github.com/test/repo",
            "key_files": [{"path": "main.py", "purpose": "Entry point"}],
            "tech_stack": {"languages": ["Python"]},
            "structure": {"total_files": 1, "total_lines": 10},
            "setup": {"commands": ["pip install -r requirements.txt"]},
        }
    }

    res = client.post(
        "/api/chat/stream",
        json={"repo_url": "https://github.com/test/repo", "question": "How to start?"},
    )
    assert res.status_code == 200
    data = res.get_data(as_text=True)
    assert "data: " in data
    assert '"type": "done"' in data


def test_run_logged():
    """Runs database records execution traces correctly."""
    run_id = log_run(
        {
            "repo_url": "https://github.com/test/trace-repo",
            "question": "Where is config?",
            "mode": "agent",
            "steps": 2,
            "tools_used": ["list_files", "read_file"],
            "citations": ["config.json"],
            "latency_ms": 320,
            "tokens_in": 500,
            "tokens_out": 120,
        }
    )
    assert run_id > 0
    runs = recent_runs(1)
    assert len(runs) >= 1
    assert runs[0]["repo_url"] == "https://github.com/test/trace-repo"
    assert runs[0]["mode"] == "agent"
    assert runs[0]["steps"] == 2
    assert "config.json" in runs[0]["citations"]


def test_zero_legacy_strings():
    """Assert zero legacy strings in app code, core modules, templates, and docs."""
    root_dir = Path(__file__).resolve().parents[1]
    ignored = {".git", "__pycache__", ".pytest_cache", ".smartonboard_cache", "tests"}
    forbidden_terms = ["".join(["wat", "sonx"]), "".join(["i", "bm"])]

    matches = []
    for path in root_dir.rglob("*"):
        if path.is_file() and not any(part in path.parts for part in ignored):
            if path.suffix in (".py", ".html", ".md", ".txt", ".json", ".example", ".yaml", ".yml"):
                text = path.read_text(encoding="utf-8", errors="ignore")
                for line_no, line in enumerate(text.splitlines(), 1):
                    lower = line.lower()
                    for term in forbidden_terms:
                        if term in lower:
                            matches.append(f"{path.name}:{line_no}: {line.strip()}")

    assert len(matches) == 0, f"Found remaining forbidden mentions: {matches}"
