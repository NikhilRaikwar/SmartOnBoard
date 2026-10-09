import json
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _get_cache_dir() -> Path:
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or not os.access(".", os.W_OK):
        return Path(tempfile.gettempdir()) / ".smartonboard_cache"
    return Path(".smartonboard_cache")


def _get_db_path() -> Path:
    return _get_cache_dir() / "runs.db"


def _init_runs_db() -> None:
    cache_dir = _get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    db_path = _get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                repo_url TEXT,
                question TEXT,
                mode TEXT,
                steps INTEGER,
                tools_used TEXT,
                citations TEXT,
                latency_ms INTEGER,
                tokens_in INTEGER,
                tokens_out INTEGER,
                error TEXT
            )
            """
        )


def log_run(data: Dict[str, Any]) -> int:
    """Log an agent or deterministic execution run safely."""
    try:
        _init_runs_db()
        ts = data.get("ts") or datetime.now().isoformat()
        repo_url = data.get("repo_url") or ""
        question = data.get("question") or ""
        mode = data.get("mode") or "deterministic"
        steps = int(data.get("steps") or 0)
        tools_used = json.dumps(data.get("tools_used") or [])
        citations = json.dumps(data.get("citations") or [])
        latency_ms = int(data.get("latency_ms") or 0)
        tokens_in = int(data.get("tokens_in") or 0)
        tokens_out = int(data.get("tokens_out") or 0)
        error = data.get("error")

        with sqlite3.connect(_get_db_path()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO agent_runs (
                    timestamp, repo_url, question, mode, steps,
                    tools_used, citations, latency_ms, tokens_in, tokens_out, error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    repo_url,
                    question,
                    mode,
                    steps,
                    tools_used,
                    citations,
                    latency_ms,
                    tokens_in,
                    tokens_out,
                    error,
                ),
            )
            return cursor.lastrowid or 0
    except Exception:
        return 0


def recent_runs(n: int = 20) -> List[Dict[str, Any]]:
    """Fetch the latest n execution traces safely."""
    try:
        _init_runs_db()
        with sqlite3.connect(_get_db_path()) as conn:
            rows = conn.execute(
                """
                SELECT id, timestamp, repo_url, question, mode, steps,
                       tools_used, citations, latency_ms, tokens_in, tokens_out, error
                FROM agent_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (n,),
            ).fetchall()

        runs = []
        for r in rows:
            runs.append(
                {
                    "id": r[0],
                    "timestamp": r[1],
                    "repo_url": r[2],
                    "question": r[3],
                    "mode": r[4],
                    "steps": r[5],
                    "tools_used": json.loads(r[6]) if r[6] else [],
                    "citations": json.loads(r[7]) if r[7] else [],
                    "latency_ms": r[8],
                    "tokens_in": r[9],
                    "tokens_out": r[10],
                    "error": r[11],
                }
            )
        return runs
    except Exception:
        return []

