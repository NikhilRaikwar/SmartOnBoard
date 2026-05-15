"""
SmartOnboard Flask application.

Real MVP behavior:
- clone a public GitHub repository
- analyze actual files and manifests
- generate a role-specific onboarding guide
- optionally polish output with watsonx.ai when configured
- serve chat/export APIs from cached real analysis
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS

from core.analyzer_real import RepositoryAnalyzer, summarize_for_question
from core.content_generator import ContentGenerator
from core.watsonx_enhancer_real import WatsonxEnhancer


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_REPO_SIZE_MB", "500")) * 1024 * 1024
CORS(app)

TEMP_DIR = tempfile.gettempdir()
ANALYSIS_CACHE: Dict[str, Dict[str, Any]] = {}


def get_watsonx() -> WatsonxEnhancer:
    return WatsonxEnhancer(
        api_key=os.getenv("WATSONX_API_KEY"),
        project_id=os.getenv("WATSONX_PROJECT_ID"),
        url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
        model_id=os.getenv("WATSONX_MODEL_ID", "meta-llama/llama-3-3-70b-instruct"),
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/analyzing")
def analyzing():
    return render_template("analyzing.html")


@app.route("/api/health", methods=["GET"])
def health_check():
    watsonx = get_watsonx()
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "watsonx": watsonx.status(),
            "cache_entries": len(ANALYSIS_CACHE),
        }
    )


@app.route("/api/analyze", methods=["POST"])
def analyze_repository():
    data = request.get_json(silent=True) or {}
    repo_url = (data.get("repo_url") or "").strip()
    role = data.get("role", "engineer")
    use_watsonx = bool(data.get("use_watsonx", True))

    if role not in {"engineer", "manager", "architect"}:
        role = "engineer"
    if not repo_url:
        return jsonify({"status": "error", "message": "Repository URL is required."}), 400

    cache_key = f"{repo_url}:{role}:{use_watsonx}"
    if cache_key in ANALYSIS_CACHE:
        return jsonify({"status": "success", "cached": True, "data": ANALYSIS_CACHE[cache_key]})

    analyzer = None
    started = datetime.now()
    try:
        analyzer = RepositoryAnalyzer(repo_url, max_files=int(os.getenv("MAX_ANALYZED_FILES", "500")))
        analyzer.clone_repository()
        analysis = analyzer.analyze()
        content = ContentGenerator(analysis, role).generate_complete_guide()

        watsonx_status = {"configured": False, "available": False}
        if use_watsonx:
            watsonx = get_watsonx()
            content = watsonx.enhance_content(content, role, analysis)
            watsonx_status = watsonx.status()

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
            "watsonx": watsonx_status,
        }
        ANALYSIS_CACHE[cache_key] = result
        ANALYSIS_CACHE[f"{repo_url}:{role}"] = result
        ANALYSIS_CACHE[f"{repo_url}:engineer"] = result if role == "engineer" else ANALYSIS_CACHE.get(f"{repo_url}:engineer", result)
        return jsonify({"status": "success", "cached": False, "data": result})
    except Exception as exc:
        app.logger.exception("Analysis failed")
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        if analyzer:
            analyzer.cleanup()


@app.route("/api/chat", methods=["POST"])
def chat_with_codebase():
    data = request.get_json(silent=True) or {}
    repo_url = (data.get("repo_url") or "").strip()
    role = data.get("role", "engineer")
    question = (data.get("question") or "").strip()

    if not repo_url or not question:
        return jsonify({"status": "error", "message": "Repository URL and question are required."}), 400

    cached = ANALYSIS_CACHE.get(f"{repo_url}:{role}") or ANALYSIS_CACHE.get(f"{repo_url}:engineer")
    context = data.get("context") or {}
    analysis = (cached or {}).get("analysis") or context.get("analysis") or {}
    if not analysis:
        return jsonify({"status": "error", "message": "Analyze this repository before asking questions."}), 404
    answer = summarize_for_question(analysis, question)
    watsonx = get_watsonx()
    question_key = question.lower()
    deterministic_question = any(term in question_key for term in ["read first", "start", "where should i begin", "where do i begin"])
    if not deterministic_question:
        answer = watsonx.enhance_qa_response(question, answer, analysis)

    return jsonify(
        {
            "status": "success",
            "question": question,
            "answer": answer,
            "watsonx": watsonx.status(),
        }
    )


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
        filename = f"{safe_name}_bob_onboarding_skill_{timestamp}.md"
        mimetype = "text/markdown"
        payload = f"""# Bob Onboarding Skill Export

Generated from: {repo_url}
Generated at: {datetime.now().isoformat()}

Use this as a Bob context document or team onboarding artifact.

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
    """Repair common LLM damage where a mermaid fence becomes raw graph text."""
    if "```mermaid" in markdown_text:
        return markdown_text
    lines = markdown_text.splitlines()
    output = []
    in_mermaid = False
    for line in lines:
        stripped = line.strip()
        starts_diagram = stripped in {"graph TD", "graph TB", "flowchart TD", "sequenceDiagram"}
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
    print("SmartOnboard - AI-powered codebase onboarding accelerator")
    print(f"Server: http://localhost:{port}")
    print(f"watsonx configured: {bool(os.getenv('WATSONX_API_KEY') and os.getenv('WATSONX_PROJECT_ID'))}")
    print("=" * 64)
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
