"""
Hybrid RAG engine with AST-aware code chunking, vector embeddings,
keyword search, and Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.chunk import chunk_file
from core.llm import embed as default_embed


CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".java",
    ".rb",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".php",
    ".swift",
    ".kt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".sh",
}

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".next",
    "coverage",
    ".smartonboard_cache",
}


class RAGIndex:
    """Persistent SQLite vector + keyword hybrid code index."""

    def __init__(self, repo_url: str, cache_root: Optional[str] = None):
        self.repo_url = repo_url
        url_hash = hashlib.sha1(repo_url.encode("utf-8")).hexdigest()
        root = Path(cache_root or ".smartonboard_cache")
        self.cache_dir = root / url_hash
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "index.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_meta (
                    path TEXT PRIMARY KEY,
                    mtime REAL,
                    content_hash TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT,
                    start_line INTEGER,
                    end_line INTEGER,
                    kind TEXT,
                    name TEXT,
                    text TEXT,
                    vector TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path)")

    def build(
        self,
        repo_path: str,
        embed_fn: Optional[Callable[[List[str]], List[List[float]]]] = None,
    ) -> int:
        """Scan repository, chunk modified code files, compute embeddings, and store."""
        embed_fn = embed_fn or default_embed
        repo_dir = Path(repo_path).resolve()
        if not repo_dir.exists():
            return 0

        # Scan candidate files
        candidate_files: List[Path] = []
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file_name in files:
                suffix = Path(file_name).suffix.lower()
                if suffix in CODE_EXTENSIONS and not file_name.endswith(".min.js"):
                    candidate_files.append(Path(root) / file_name)

        # Determine modified/new files
        files_to_index: List[Tuple[Path, str, float, str]] = []
        with sqlite3.connect(self.db_path) as conn:
            stored_meta = {
                row[0]: (row[1], row[2])
                for row in conn.execute("SELECT path, mtime, content_hash FROM file_meta").fetchall()
            }

        for file_path in candidate_files:
            rel_path = file_path.relative_to(repo_dir).as_posix()
            try:
                stat = file_path.stat()
                mtime = stat.st_mtime
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                chash = hashlib.md5(text.encode("utf-8")).hexdigest()

                if rel_path in stored_meta:
                    old_mtime, old_hash = stored_meta[rel_path]
                    if abs(old_mtime - mtime) < 0.001 and old_hash == chash:
                        continue  # Cache hit, file unchanged

                files_to_index.append((file_path, rel_path, mtime, chash))
            except Exception:
                continue

        if not files_to_index:
            # All files are up to date
            with sqlite3.connect(self.db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            return count

        # Process chunks for changed files
        all_chunks: List[Dict[str, Any]] = []
        file_meta_updates: List[Tuple[str, float, str]] = []
        paths_to_clear: List[str] = []

        for file_path, rel_path, mtime, chash in files_to_index:
            paths_to_clear.append(rel_path)
            file_meta_updates.append((rel_path, mtime, chash))
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                chunks = chunk_file(rel_path, text)
                for chunk in chunks:
                    all_chunks.append(chunk.to_dict())
            except Exception:
                continue

        # Compute embeddings in batches
        texts = [c["text"] for c in all_chunks]
        vectors = embed_fn(texts) if texts else []

        with sqlite3.connect(self.db_path) as conn:
            # Clear old records for updated files
            for p in paths_to_clear:
                conn.execute("DELETE FROM chunks WHERE path = ?", (p,))
                conn.execute("DELETE FROM file_meta WHERE path = ?", (p,))

            # Insert metadata
            conn.executemany(
                "INSERT OR REPLACE INTO file_meta (path, mtime, content_hash) VALUES (?, ?, ?)",
                file_meta_updates,
            )

            # Insert new chunks
            rows = []
            for chunk, vec in zip(all_chunks, vectors):
                rows.append(
                    (
                        chunk["path"],
                        chunk["start_line"],
                        chunk["end_line"],
                        chunk["kind"],
                        chunk["name"],
                        chunk["text"],
                        json.dumps(vec),
                    )
                )
            if rows:
                conn.executemany(
                    """
                    INSERT INTO chunks (path, start_line, end_line, kind, name, text, vector)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

            total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

        return total_chunks

    def search(self, query_vec: List[float], k: int = 20) -> List[Dict[str, Any]]:
        """Cosine similarity search over chunk vectors."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, path, start_line, end_line, kind, name, text, vector FROM chunks"
            ).fetchall()

        if not rows or not query_vec:
            return []

        results: List[Tuple[float, Dict[str, Any]]] = []
        for r in rows:
            vec_json = r[7]
            if not vec_json:
                continue
            doc_vec = json.loads(vec_json)
            sim = _cosine_similarity(query_vec, doc_vec)
            item = {
                "id": r[0],
                "path": r[1],
                "start_line": r[2],
                "end_line": r[3],
                "kind": r[4],
                "name": r[5],
                "text": r[6],
                "vector_sim": sim,
            }
            results.append((sim, item))

        results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in results[:k]]

    def keyword_search(self, query: str, k: int = 100) -> List[Dict[str, Any]]:
        """Token-overlap keyword search across paths and chunk text."""
        query_tokens = set(re.findall(r"\w+", query.lower()))
        if not query_tokens:
            return []

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, path, start_line, end_line, kind, name, text FROM chunks"
            ).fetchall()

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for r in rows:
            path_tokens = set(re.findall(r"\w+", r[1].lower()))
            text_tokens = set(re.findall(r"\w+", r[6].lower()))

            # Weight path matches higher than general body text
            path_overlap = len(query_tokens & path_tokens)
            text_overlap = len(query_tokens & text_tokens)
            score = (path_overlap * 2.5) + text_overlap

            if score > 0:
                item = {
                    "id": r[0],
                    "path": r[1],
                    "start_line": r[2],
                    "end_line": r[3],
                    "kind": r[4],
                    "name": r[5],
                    "text": r[6],
                    "kw_score": score,
                }
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:k]]

    def hybrid_search(
        self,
        query: str,
        query_vec: Optional[List[float]] = None,
        k: int = 8,
        embed_fn: Optional[Callable[[List[str]], List[List[float]]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining vector cosine search and token-overlap keyword search
        using Reciprocal Rank Fusion (RRF, constant k=60).
        """
        embed_fn = embed_fn or default_embed
        if query_vec is None:
            vectors = embed_fn([query])
            query_vec = vectors[0] if vectors else []

        vec_results = self.search(query_vec, k=20)
        kw_results = self.keyword_search(query, k=100)

        # Apply Reciprocal Rank Fusion (RRF)
        RRF_CONSTANT = 60
        scores: Dict[int, float] = {}
        doc_map: Dict[int, Dict[str, Any]] = {}

        for rank, item in enumerate(vec_results, 1):
            doc_id = item["id"]
            doc_map[doc_id] = item
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (RRF_CONSTANT + rank))

        for rank, item in enumerate(kw_results, 1):
            doc_id = item["id"]
            doc_map[doc_id] = item
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (RRF_CONSTANT + rank))

        fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        final_results = []
        for doc_id, score in fused[:k]:
            item = dict(doc_map[doc_id])
            item["rrf_score"] = score
            final_results.append(item)

        return final_results


def rewrite_query(question: str, llm: Optional[Any] = None) -> str:
    """Rewrite a user question into search keywords for codebase retrieval."""
    if not question:
        return ""
    if llm is None:
        return question

    try:
        from core.llm import chat as llm_chat

        messages = [
            {
                "role": "system",
                "content": "Rewrite the user query into 3-6 space-separated code search keywords. Return ONLY the keywords.",
            },
            {"role": "user", "content": question},
        ]
        resp = llm_chat(messages, max_tokens=30, temperature=0.0, client=llm)
        content = (resp.get("content") or "").strip()
        return content if content else question
    except Exception:
        return question


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if len(v1) != len(v2) or not v1:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)
