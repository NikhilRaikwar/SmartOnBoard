"""
Optional watsonx.ai enhancement layer.

The app must remain usable during demos even if the SDK is not installed or the
API is temporarily unavailable. This adapter reports whether it is configured
and falls back to deterministic content when needed.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


class WatsonxEnhancer:
    """Thin adapter around ibm-watsonx-ai text generation."""

    def __init__(
        self,
        api_key: Optional[str],
        project_id: Optional[str],
        url: str = "https://us-south.ml.cloud.ibm.com",
        model_id: str = "meta-llama/llama-3-3-70b-instruct",
    ):
        self.api_key = api_key
        self.project_id = project_id
        self.url = url
        self.model_id = model_id
        self.available = False
        self.error: Optional[str] = None
        self.model: Any = None

        if not api_key or not project_id:
            self.error = "WATSONX_API_KEY and WATSONX_PROJECT_ID are not configured."
            return

        try:
            from ibm_watsonx_ai import Credentials
            from ibm_watsonx_ai.foundation_models import Model

            credentials = Credentials(url=url, api_key=api_key)
            self.model = Model(
                model_id=model_id,
                credentials=credentials,
                project_id=project_id,
                params={
                    "decoding_method": "greedy",
                    "max_new_tokens": 2500,
                    "temperature": 0.25,
                    "top_p": 0.9,
                    "repetition_penalty": 1.05,
                },
            )
            self.available = True
        except Exception as exc:  # SDK missing, auth issue, or model issue.
            self.error = str(exc)
            # The REST path is validated lazily on first generation. This keeps
            # the app usable when the SDK is not installed but requests is.
            try:
                import requests  # noqa: F401

                self.available = True
                self.model = None
                self.error = None
            except Exception:
                pass

    def status(self) -> Dict[str, Any]:
        return {
            "configured": bool(self.api_key and self.project_id),
            "available": self.available,
            "model_id": self.model_id,
            "error": self.error,
        }

    def enhance_content(self, content: str, role: str, analysis: Optional[Dict[str, Any]] = None) -> str:
        if not self.available:
            return content
        prompt = f"""You are formatting an onboarding guide for a {role}.

Rules:
- Preserve factual claims from the source.
- Keep markdown structure.
- Preserve fenced code blocks exactly, especially ```mermaid blocks.
- Keep lists as real markdown lists with line breaks.
- Preserve markdown tables.
- Do not collapse metadata, dependencies, setup commands, or script lists into one paragraph.
- Make the guide polished, concrete, and role-specific.
- Do not invent repository details that are not in the source.
- Keep Mermaid diagrams valid.

Source guide:
{content[:9000]}

Improved markdown guide:"""
        return self._generate(prompt, fallback=content)

    def enhance_qa_response(self, question: str, answer: str, context: Dict[str, Any]) -> str:
        if not self.available:
            return answer
        prompt = f"""Answer this codebase question for a developer.

Rules:
- Return only the final answer.
- Keep it under 5 bullets or 90 words.
- Do not include drafts, revisions, alternatives, notes, or phrases like "final version".
- Do not mention prompts, source text, or that the answer was improved.
- Stay grounded in the repository context.
- Do not add extra recommendations beyond the baseline facts unless directly asked.

Question: {question}

Baseline facts:
{answer}

Repository context:
{str(context)[:3500]}

Final answer:"""
        response = self._generate(prompt, fallback=answer, max_chars=1200)
        return self._clean_qa_response(response, fallback=answer)

    def _clean_qa_response(self, response: str, fallback: str) -> str:
        cleaned = (response or "").strip()
        if not cleaned:
            return fallback

        marker_patterns = [
            r"(?is)here is the final version(?: after [^:\n]+)?:\s*",
            r"(?is)the final answer is\s*",
            r"(?is)final answer:\s*",
            r"(?is)final version:\s*",
        ]
        for pattern in marker_patterns:
            matches = list(re.finditer(pattern, cleaned))
            if matches:
                cleaned = cleaned[matches[-1].end() :].strip()

        stop_patterns = [
            r"(?is)\n\s*however,\s+the above response\b.*",
            r"(?is)\n\s*note:\s+the above response\b.*",
            r"(?is)\n\s*here is the revised version\b.*",
            r"(?is)\n\s*here is the final version\b.*",
        ]
        for pattern in stop_patterns:
            cleaned = re.sub(pattern, "", cleaned).strip()

        banned = ["draft answer", "improved answer", "source text", "final version after"]
        if any(token in cleaned.lower() for token in banned):
            return fallback

        cleaned = self._dedupe_and_limit_lines(cleaned)
        cleaned = self._trim_to_complete_boundary(cleaned, max_chars=900)
        return cleaned or fallback

    def _dedupe_and_limit_lines(self, text: str, max_lines: int = 5) -> str:
        kept = []
        seen = set()
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                if kept and kept[-1] != "":
                    kept.append("")
                continue

            normalized = re.sub(r"^[\-*]\s*", "", line.lower())
            normalized = re.sub(r"^\d+[\.)]\s*", "", normalized)
            normalized = re.sub(r"`", "", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip(" .:")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            kept.append(line)

            content_lines = [item for item in kept if item]
            if len(content_lines) >= max_lines:
                break

        return "\n".join(kept).strip()

    def _trim_to_complete_boundary(self, text: str, max_chars: int) -> str:
        cleaned = text.strip()
        if len(cleaned) <= max_chars:
            return cleaned

        clipped = cleaned[:max_chars].rstrip()
        boundaries = [
            clipped.rfind("\n- "),
            clipped.rfind("\n* "),
            clipped.rfind("\n"),
            clipped.rfind(". "),
            clipped.rfind("! "),
            clipped.rfind("? "),
        ]
        boundary = max(boundaries)
        if boundary > max_chars * 0.45:
            clipped = clipped[: boundary + 1].rstrip()
        else:
            clipped = clipped.rsplit(" ", 1)[0].rstrip()
        return clipped.rstrip(" ,;:-") + ("." if clipped and clipped[-1].isalnum() else "")

    def _generate(self, prompt: str, fallback: str, max_chars: int = 12000) -> str:
        try:
            if self.model is None:
                response = self._generate_rest(prompt)
            else:
                response = self.model.generate_text(prompt=prompt)
            if isinstance(response, str) and response.strip():
                return response.strip()[:max_chars]
            return fallback
        except Exception as exc:
            self.error = str(exc)
            self.available = False
            return fallback

    def _generate_rest(self, prompt: str) -> str:
        import requests

        token_response = requests.post(
            "https://iam.cloud.ibm.com/identity/token",
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": self.api_key,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        token_response.raise_for_status()
        token = token_response.json()["access_token"]

        generation_response = requests.post(
            f"{self.url.rstrip('/')}/ml/v1/text/generation?version=2023-05-29",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "model_id": self.model_id,
                "project_id": self.project_id,
                "input": prompt,
                "parameters": {
                    "decoding_method": "greedy",
                    "max_new_tokens": 1800,
                    "temperature": 0.25,
                    "top_p": 0.9,
                    "repetition_penalty": 1.05,
                },
            },
            timeout=90,
        )
        generation_response.raise_for_status()
        payload = generation_response.json()
        results = payload.get("results") or []
        if results:
            return results[0].get("generated_text", "")
        return ""
