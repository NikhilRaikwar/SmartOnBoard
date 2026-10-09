"""
AST-aware and sliding-window code chunking for SmartOnboard RAG.

Extracts semantic chunks (classes, top-level functions) for Python files,
and sliding windows with contextual headers for other programming languages.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class Chunk:
    path: str
    start_line: int
    end_line: int
    kind: str
    name: str
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def chunk_file(path: str, text: str) -> List[Chunk]:
    """
    Chunk source code into semantic or sliding-window chunks with context headers.
    """
    if not text or not text.strip():
        return []

    clean_path = str(Path(path).as_posix())
    lines = text.splitlines()

    # Attempt AST parsing for Python files
    if clean_path.endswith(".py"):
        try:
            tree = ast.parse(text)
            chunks: List[Chunk] = []

            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    kind = "class" if isinstance(node, ast.ClassDef) else "function"
                    start_line = node.lineno
                    end_line = getattr(node, "end_lineno", None)
                    if end_line is None:
                        # Fallback for Python versions without end_lineno
                        end_line = min(len(lines), start_line + 40)

                    chunk_lines = lines[start_line - 1 : end_line]
                    body_text = "\n".join(chunk_lines)
                    header = f"[{clean_path} | {kind} {node.name} L{start_line}-L{end_line}]"
                    full_text = f"{header}\n{body_text}"

                    chunks.append(
                        Chunk(
                            path=clean_path,
                            start_line=start_line,
                            end_line=end_line,
                            kind=kind,
                            name=node.name,
                            text=full_text,
                        )
                    )

            if chunks:
                return chunks
        except (SyntaxError, Exception):
            # Fall back to sliding window on parse errors
            pass

    # Sliding window chunking (40 lines, 10 overlap)
    return _sliding_window_chunk(clean_path, lines, window_size=40, overlap=10)


def _sliding_window_chunk(
    path: str,
    lines: List[str],
    window_size: int = 40,
    overlap: int = 10,
) -> List[Chunk]:
    chunks: List[Chunk] = []
    total_lines = len(lines)
    step = max(1, window_size - overlap)

    for i in range(0, total_lines, step):
        start_line = i + 1
        end_line = min(total_lines, i + window_size)
        chunk_lines = lines[i:end_line]
        body_text = "\n".join(chunk_lines)
        if not body_text.strip():
            continue

        header = f"[{path} | L{start_line}-L{end_line}]"
        full_text = f"{header}\n{body_text}"

        chunks.append(
            Chunk(
                path=path,
                start_line=start_line,
                end_line=end_line,
                kind="block",
                name=f"L{start_line}-L{end_line}",
                text=full_text,
            )
        )

        if end_line >= total_lines:
            break

    return chunks
