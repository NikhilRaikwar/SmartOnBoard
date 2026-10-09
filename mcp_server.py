"""
SmartOnboard Model Context Protocol (MCP) Server.

Exposes read-only repository inspection tools and onboarding guide generation
over standard input/output (stdio) JSON-RPC 2.0 for Claude Code, Cursor, and MCP clients.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.agent import execute_tool
from core.analyzer_real import RepositoryAnalyzer
from core.content_generator import ContentGenerator


def handle_list_tools() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "list_files",
                "description": "List files in a repository matching an optional regex pattern (read-only).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Absolute or relative path to repository."},
                        "pattern": {"type": "string", "description": "Optional filter pattern."},
                    },
                    "required": ["repo_path"],
                },
            },
            {
                "name": "read_file",
                "description": "Safely read up to 4000 characters from a repository file (path traversal guarded).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Repository path."},
                        "path": {"type": "string", "description": "Relative file path within repository."},
                        "max_chars": {"type": "integer", "description": "Max characters to read."},
                    },
                    "required": ["repo_path", "path"],
                },
            },
            {
                "name": "search_code",
                "description": "Search for a regex/text pattern across repository files (max 20 hits).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Repository path."},
                        "pattern": {"type": "string", "description": "Search regex pattern."},
                    },
                    "required": ["repo_path", "pattern"],
                },
            },
            {
                "name": "get_setup_info",
                "description": "Extract deterministic setup commands and package scripts from manifests.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Repository path."},
                    },
                    "required": ["repo_path"],
                },
            },
            {
                "name": "generate_onboarding_guide",
                "description": "Generate a full grounded onboarding guide for a local repository directory.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Repository path."},
                        "role": {"type": "string", "enum": ["engineer", "manager", "architect"], "default": "engineer"},
                    },
                    "required": ["repo_path"],
                },
            },
        ]
    }


def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    repo_path = arguments.get("repo_path") or "."
    analysis: Dict[str, Any] = {}

    if name in ("list_files", "read_file", "search_code", "get_setup_info"):
        output, summary = execute_tool(
            name=name,
            args=arguments,
            repo_path=repo_path,
            analysis=analysis,
        )
        return {"content": [{"type": "text", "text": output}], "summary": summary}

    elif name == "generate_onboarding_guide":
        role = arguments.get("role", "engineer")
        target_dir = Path(repo_path).resolve()
        analyzer = RepositoryAnalyzer("https://github.com/local/repo")
        analyzer.repo_path = str(target_dir)
        analyzer.repo_name = target_dir.name
        analyzer.owner = "local"
        analysis_data = analyzer.analyze()
        content = ContentGenerator(analysis_data, role).generate_complete_guide()
        return {"content": [{"type": "text", "text": content}]}

    return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}


def run_stdio_server():
    """Main JSON-RPC stdio event loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params") or {}

            if method == "tools/list":
                res = handle_list_tools()
                resp = {"jsonrpc": "2.0", "id": req_id, "result": res}
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments") or {}
                res = handle_call_tool(tool_name, tool_args)
                resp = {"jsonrpc": "2.0", "id": req_id, "result": res}
            elif method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "smartonboard-mcp", "version": "1.0.0"},
                        "capabilities": {"tools": {}},
                    },
                }
            else:
                resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method {method} not found"}}

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as exc:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(exc)}}
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
