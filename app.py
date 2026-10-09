"""
SmartOnboard Flask application.

Architecture:
- Deterministic analysis for facts (stack, manifests, entry points, structure)
- AST-aware chunking and hybrid RAG (sqlite-vec + BM25/keyword retrieval with RRF)
- Tool-calling ReAct agent for codebase reasoning and multi-turn Q&A
- Full execution observability and run tracing
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, render_template, request, send_file
from flask_cors import CORS

from core.analyzer_real import RepositoryAnalyzer, summarize_for_question
from core.content_generator import ContentGenerator
from core.llm import LLMUnavailable, llm_status
from core.rag import RAGIndex
from core.agent import run_agent, run_agent_stream
from core.runs import log_run, recent_runs


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_REPO_SIZE_MB", "500")) * 1024 * 1024
CORS(app)

TEMP_DIR = tempfile.gettempdir()
ANALYSIS_CACHE: Dict[str, Any] = {}


def is_agent_enabled() -> bool:
    return os.environ.get("AGENT_QA_ENABLED", "false").strip().lower() == "true"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/favicon.ico")
def favicon():
    return send_file(BASE_DIR / "docs" / "images" / "favicon.svg", mimetype="image/svg+xml")


@app.route("/favicon.svg")
def favicon_svg():
    return send_file(BASE_DIR / "docs" / "images" / "favicon.svg", mimetype="image/svg+xml")


@app.route("/assets/<path:filename>")
def image_asset(filename: str):
    assets_dir = (BASE_DIR / "docs" / "images").resolve()
    target = (assets_dir / filename).resolve()
    if not str(target).startswith(str(assets_dir)) or not target.is_file():
        abort(404)
    return send_file(target)


@app.route("/analyzing")
def analyzing():
    return render_template("analyzing.html")


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "agent_enabled": is_agent_enabled(),
            "llm": llm_status(),
            "cache_entries": len(ANALYSIS_CACHE),
        }
    )


@app.route("/api/analyze", methods=["POST"])
def analyze_repository():
    data = request.get_json(silent=True) or {}
    repo_url = (data.get("repo_url") or "").strip()
    role = data.get("role", "engineer")

    if role not in {"engineer", "manager", "architect"}:
        role = "engineer"
    if not repo_url:
        return jsonify({"status": "error", "message": "Repository URL is required."}), 400

    cache_key = f"{repo_url}:{role}"
    if cache_key in ANALYSIS_CACHE:
        return jsonify({"status": "success", "cached": True, "data": ANALYSIS_CACHE[cache_key]})

    analyzer = None
    started = datetime.now()
    try:
        analyzer = RepositoryAnalyzer(repo_url, max_files=int(os.getenv("MAX_ANALYZED_FILES", "500")))
        analyzer.clone_repository()
        analysis = analyzer.analyze()
        content = ContentGenerator(analysis, role).generate_complete_guide()

        # Build / update persistent hybrid RAG index
        try:
            rag = RAGIndex(repo_url)
            rag.build(analyzer.repo_path)
        except Exception as rag_exc:
            app.logger.warning(f"RAG indexing skipped or failed: {rag_exc}")

        elapsed = max(1, int((datetime.now() - started).total_seconds()))
        result = {
            "repo_url": analysis["repo_url"],
            "repo_name": analysis["repo_name"],
            "role": role,
            "tech_stack": analysis["tech_stack"],
            "structure": analysis["structure"],
            "key_files": analysis["key_files"],
            "analysis": analysis,
            "content": content,
            "analysis_time": f"{elapsed}s",
            "generated_at": datetime.now().isoformat(),
        }

        # Cache results and preserve cloned path for agent tools
        ANALYSIS_CACHE[cache_key] = result
        ANALYSIS_CACHE[f"{repo_url}:{role}"] = result
        ANALYSIS_CACHE[f"{repo_url}:engineer"] = result if role == "engineer" else ANALYSIS_CACHE.get(f"{repo_url}:engineer", result)
        if analyzer.repo_path:
            ANALYSIS_CACHE[f"{repo_url}:path"] = analyzer.repo_path

        return jsonify({"status": "success", "cached": False, "data": result})
    except Exception as exc:
        app.logger.exception("Analysis failed")
        if analyzer:
            analyzer.cleanup()
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/chat", methods=["POST"])
def chat_with_codebase():
    data = request.get_json(silent=True) or {}
    repo_url = (data.get("repo_url") or "").strip()
    role = data.get("role", "engineer")
    question = (data.get("question") or "").strip()
    history = data.get("history") or []

    if not repo_url or not question:
        return jsonify({"status": "error", "message": "Repository URL and question are required."}), 400

    cached = ANALYSIS_CACHE.get(f"{repo_url}:{role}") or ANALYSIS_CACHE.get(f"{repo_url}:engineer")
    context = data.get("context") or {}
    analysis = (cached or {}).get("analysis") or context.get("analysis") or (context if context.get("structure") else {})
    if not analysis:
        return jsonify({"status": "error", "message": "Analyze this repository before asking questions."}), 404

    started = time.time()
    question_key = question.lower()
    deterministic_question = any(
        term in question_key
        for term in ["read first", "start", "where should i begin", "where do i begin"]
    )

    # 1. Deterministic instant response for onboarding start questions
    if deterministic_question:
        answer = summarize_for_question(analysis, question)
        citations = [kf["path"] for kf in analysis.get("key_files", [])[:4] if "path" in kf]
        latency_ms = int((time.time() - started) * 1000)
        log_run(
            {
                "repo_url": repo_url,
                "question": question,
                "mode": "deterministic",
                "steps": 0,
                "tools_used": [],
                "citations": citations,
                "latency_ms": latency_ms,
                "tokens_in": 0,
                "tokens_out": 0,
            }
        )
        return jsonify(
            {
                "status": "success",
                "mode": "deterministic",
                "question": question,
                "answer": answer,
                "citations": citations,
                "steps": 0,
            }
        )

    # 2. Agent reasoning when AGENT_QA_ENABLED is true
    if is_agent_enabled():
        repo_path = ANALYSIS_CACHE.get(f"{repo_url}:path") or "."
        rag = RAGIndex(repo_url)
        try:
            agent_res = run_agent(
                question=question,
                repo_path=repo_path,
                analysis=analysis,
                rag=rag,
                history=history,
            )
            latency_ms = int((time.time() - started) * 1000)
            log_run(
                {
                    "repo_url": repo_url,
                    "question": question,
                    "mode": "agent",
                    "steps": agent_res["steps"],
                    "tools_used": ["rag_search", "inspect_files"],
                    "citations": agent_res["citations"],
                    "latency_ms": latency_ms,
                    "tokens_in": agent_res["usage"]["in"],
                    "tokens_out": agent_res["usage"]["out"],
                }
            )
            return jsonify(
                {
                    "status": "success",
                    "mode": "agent",
                    "question": question,
                    "answer": agent_res["answer"],
                    "citations": agent_res["citations"],
                    "steps": agent_res["steps"],
                    "usage": agent_res["usage"],
                }
            )
        except Exception as exc:
            app.logger.warning(f"Agent execution failed, falling back to deterministic response: {exc}")
            answer = summarize_for_question(analysis, question)
            latency_ms = int((time.time() - started) * 1000)
            log_run(
                {
                    "repo_url": repo_url,
                    "question": question,
                    "mode": "deterministic-fallback",
                    "steps": 0,
                    "tools_used": [],
                    "citations": [],
                    "latency_ms": latency_ms,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "error": str(exc),
                }
            )
            return jsonify(
                {
                    "status": "success",
                    "mode": "deterministic-fallback",
                    "question": question,
                    "answer": answer,
                    "citations": [],
                    "steps": 0,
                    "fallback": True,
                }
            )

    # 3. Deterministic baseline response when agent is disabled
    answer = summarize_for_question(analysis, question)
    latency_ms = int((time.time() - started) * 1000)
    log_run(
        {
            "repo_url": repo_url,
            "question": question,
            "mode": "deterministic",
            "steps": 0,
            "tools_used": [],
            "citations": [],
            "latency_ms": latency_ms,
            "tokens_in": 0,
            "tokens_out": 0,
        }
    )
    return jsonify(
        {
            "status": "success",
            "mode": "deterministic",
            "question": question,
            "answer": answer,
            "citations": [],
            "steps": 0,
        }
    )


@app.route("/api/chat/stream", methods=["POST"])
def chat_with_codebase_stream():
    if not is_agent_enabled():
        return jsonify({"error": "agent disabled"}), 403

    data = request.get_json(silent=True) or {}
    repo_url = (data.get("repo_url") or "").strip()
    role = data.get("role", "engineer")
    question = (data.get("question") or "").strip()
    history = data.get("history") or []

    if not repo_url or not question:
        return jsonify({"status": "error", "message": "Repository URL and question are required."}), 400

    cached = ANALYSIS_CACHE.get(f"{repo_url}:{role}") or ANALYSIS_CACHE.get(f"{repo_url}:engineer")
    context = data.get("context") or {}
    analysis = (cached or {}).get("analysis") or context.get("analysis") or (context if context.get("structure") else {})
    if not analysis:
        return jsonify({"status": "error", "message": "Analyze this repository before asking questions."}), 404

    repo_path = ANALYSIS_CACHE.get(f"{repo_url}:path") or "."
    rag = RAGIndex(repo_url)

    def generate_events() -> Generator[str, None, None]:
        started = time.time()
        final_answer = ""
        citations = []
        steps = 0
        usage = {"in": 0, "out": 0}
        try:
            for event in run_agent_stream(
                question=question,
                repo_path=repo_path,
                analysis=analysis,
                rag=rag,
                history=history,
            ):
                if event.get("type") == "done":
                    final_answer = event.get("answer", "")
                    citations = event.get("citations", [])
                    steps = event.get("steps", 0)
                    usage = event.get("usage", usage)
                yield f"data: {json.dumps(event)}\n\n"

            latency_ms = int((time.time() - started) * 1000)
            log_run(
                {
                    "repo_url": repo_url,
                    "question": question,
                    "mode": "agent",
                    "steps": steps,
                    "tools_used": ["stream_agent"],
                    "citations": citations,
                    "latency_ms": latency_ms,
                    "tokens_in": usage.get("in", 0),
                    "tokens_out": usage.get("out", 0),
                }
            )
        except Exception as exc:
            app.logger.warning(f"Streaming agent failed: {exc}")
            fallback_answer = summarize_for_question(analysis, question)
            done_event = {
                "type": "done",
                "answer": fallback_answer,
                "citations": [],
                "steps": 0,
                "usage": {"in": 0, "out": 0},
                "fallback": True,
            }
            yield f"data: {json.dumps(done_event)}\n\n"

    return Response(generate_events(), mimetype="text/event-stream")


@app.route("/api/runs", methods=["GET"])
def get_runs():
    runs = recent_runs(20)
    return jsonify({"status": "success", "runs": runs})


@app.route("/api/export/<export_format>", methods=["POST"])
def export_guide(export_format: str):
    data = request.get_json(silent=True) or {}
    content = data.get("content")
    repo_url = data.get("repo_url", "unknown-repo")

    if not content:
        return jsonify({"status": "error", "message": "Content is required."}), 400

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = repo_url.rstrip("/").split("/")[-1] or "onboarding"

    if export_format == "html":
        html_content = render_template(
            "export.html",
            content=_markdown_to_html(content),
            generated_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        filename = f"{safe_name}_onboarding_{timestamp}.html"
        mimetype = "text/html"
        payload = html_content
    elif export_format in {"markdown", "md"}:
        filename = f"{safe_name}_onboarding_{timestamp}.md"
        mimetype = "text/markdown"
        payload = content
    elif export_format == "skill":
        filename = f"{safe_name}_onboarding_skill_{timestamp}.md"
        mimetype = "text/markdown"
        payload = f"""# Codebase Onboarding Skill

Generated from: {repo_url}
Generated at: {datetime.now().isoformat()}

Use this skill with AI coding agents and MCP clients for deep context.

{content}
"""
    else:
        return jsonify({"status": "error", "message": f"Unsupported export format: {export_format}"}), 400

    filepath = os.path.join(TEMP_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as handle:
        handle.write(payload)
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype=mimetype)


def _markdown_to_html(markdown_text: str) -> str:
    try:
        import markdown

        normalized = _restore_mermaid_fences(markdown_text)
        html = markdown.markdown(normalized, extensions=["fenced_code", "tables"])
        return _convert_mermaid_pre_blocks(html)
    except Exception:
        escaped = (
            markdown_text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return f"<pre>{escaped}</pre>"


def _restore_mermaid_fences(markdown_text: str) -> str:
    if "```mermaid" in markdown_text:
        return markdown_text
    lines = markdown_text.splitlines()
    output = []
    in_mermaid = False
    for line in lines:
        stripped = line.strip()
        starts_diagram = stripped in {"graph TD", "graph TB", "flowchart TD", "flowchart LR", "sequenceDiagram"}
        if starts_diagram and not in_mermaid:
            output.append("```mermaid")
            output.append(line)
            in_mermaid = True
            continue
        if in_mermaid and stripped.startswith(("## ", "### ", "How to Read", "4. ", "5. ")):
            output.append("```")
            in_mermaid = False
        output.append(line)
    if in_mermaid:
        output.append("```")
    return "\n".join(output)


def _convert_mermaid_pre_blocks(html: str) -> str:
    import re
    from html import unescape

    pattern = re.compile(r'<pre><code class="language-mermaid">(.*?)</code></pre>', re.DOTALL)

    def replace(match):
        return f'<div class="mermaid">{unescape(match.group(1)).strip()}</div>'

    return pattern.sub(replace, html)


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"status": "error", "message": "Not found."}), 404


@app.errorhandler(500)
def internal_error(_error):
    return jsonify({"status": "error", "message": "Internal server error."}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    print("=" * 64)
    print("SmartOnboard - Codebase Onboarding Accelerator (AI Engineer Upgrade)")
    print(f"Server: http://localhost:{port}")
    print(f"LLM Status: {llm_status()}")
    print(f"Agent QA Enabled: {is_agent_enabled()}")
    print("=" * 64)
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
