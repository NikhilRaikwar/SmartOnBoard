"""
Markdown onboarding guide generator.

The generator is deterministic and grounded in the real repository analysis
data. watsonx.ai can later polish this markdown, but the base output is already
usable when API credentials or SDKs are unavailable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List
import re


class ContentGenerator:
    """Generate a role-specific onboarding guide from repository analysis."""

    def __init__(self, analysis: Dict[str, Any], role: str):
        self.analysis = analysis
        self.role = role if role in {"engineer", "manager", "architect"} else "engineer"

    def generate_complete_guide(self) -> str:
        sections = [
            self._header(),
            self._executive_summary(),
            self._tech_stack(),
            self._architecture(),
            self._key_files(),
            self._critical_logic(),
            self._setup(),
            self._testing(),
            self._start_here(),
            self._role_specific(),
            self._bob_reuse(),
        ]
        return "\n\n---\n\n".join(section.strip() for section in sections if section.strip())

    def _header(self) -> str:
        return f"""# SmartOnboard Guide: {self.analysis.get('repo_name', 'Repository')}

| Field | Value |
|---|---|
| Generated | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| Repository | {self.analysis.get('repo_url', 'Unknown')} |
| Role | {self.role.title()} |
| Source | Real repository clone and file scan |"""

    def _executive_summary(self) -> str:
        readme = self.analysis.get("readme") or ""
        first_para = self._first_readme_paragraph(readme)
        structure = self.analysis.get("structure", {})
        tech = self.analysis.get("tech_stack", {})

        return f"""## 1. Project Overview

{first_para or "No README summary was found, so this overview is based on repository structure and detected files."}

### Fast Facts

- Files scanned: {structure.get('total_files', 0)}
- Lines scanned: {structure.get('total_lines', 0)}
- Primary languages: {self._join(tech.get('languages', []))}
- Frameworks: {self._join(tech.get('frameworks', []))}
- Entry points: {self._join_code(structure.get('entry_points', []))}
- Main directories: {self._join_code(structure.get('directories', []))}"""

    def _tech_stack(self) -> str:
        tech = self.analysis.get("tech_stack", {})
        dependencies = tech.get("dependencies", {})
        dependency_lines: List[str] = []
        for manifest, deps in dependencies.items():
            if isinstance(deps, dict):
                names = list(deps.keys())[:12]
            else:
                names = [str(dep).split("=")[0].split(">")[0].split("<")[0] for dep in deps[:12]]
            dependency_lines.append(f"- `{manifest}`: {self._join_code(names)}")

        return f"""## 2. Tech Stack and Dependencies

- Languages: {self._join(tech.get('languages', []))}
- Frameworks: {self._join(tech.get('frameworks', []))}
- Package managers: {self._join(tech.get('package_managers', []))}
- Build tools: {self._join(tech.get('build_tools', []))}
- Databases: {self._join(tech.get('databases', []))}
- Testing tools: {self._join(tech.get('testing', []))}

### Notable Dependencies

{chr(10).join(dependency_lines) if dependency_lines else "- No dependency manifest was detected in the scanned files."}"""

    def _architecture(self) -> str:
        structure = self.analysis.get("structure", {})
        dirs = structure.get("directories", [])
        entries = structure.get("entry_points", [])
        configs = structure.get("config_files", [])

        dir_nodes = "\n".join(
            f"    App --> D{i}[{self._mermaid_label(directory)}]" for i, directory in enumerate(dirs[:8], 1)
        )
        if not dir_nodes:
            dir_nodes = "    App --> Files[Repository files]"

        return f"""## 3. Architecture Summary

The repository appears to start from {self._join_code(entries) if entries else "standard entry points were not detected automatically"} and is organized around {self._join_code(dirs)}.
Configuration and runtime behavior are likely controlled by {self._join_code(configs)}.

```mermaid
graph TD
    Repo[{self._mermaid_label(self.analysis.get('repo_name', 'Repository'))}] --> App[Application Surface]
{dir_nodes}
    App --> Config[Configuration]
    Config --> Runtime[Local / CI Runtime]
```

### How to Read This Architecture

1. Start at the detected entry point or README.
2. Follow imports or route registration into the main source directories.
3. Read configuration files next because they explain scripts, environment variables, and service dependencies.
4. Use test files to confirm expected behavior."""

    def _key_files(self) -> str:
        files = self.analysis.get("key_files", [])
        if not files:
            return "## 4. Key File Map\n\nNo key files were detected automatically."
        rows = ["| File | Why it matters | Lines |", "|---|---|---|"]
        for item in files[:12]:
            rows.append(f"| `{item['path']}` | {item['purpose']} | {item.get('lines', 0)} |")
        return "## 4. Key File Map\n\n" + "\n".join(rows)

    def _critical_logic(self) -> str:
        snippets = self.analysis.get("snippets", {})
        if not snippets:
            return "## 5. Critical Logic Walkthrough\n\nNo readable snippets were extracted from key files."

        blocks = []
        for path, text in list(snippets.items())[:5]:
            summary = self._summarize_snippet(path, text)
            blocks.append(f"### `{path}`\n\n{summary}")
        return "## 5. Critical Logic Walkthrough\n\n" + "\n\n".join(blocks)

    def _setup(self) -> str:
        setup = self.analysis.get("setup", {})
        commands = setup.get("commands", [])
        scripts = setup.get("scripts", [])
        command_block = "\n".join(commands) if commands else "# No setup commands inferred"
        script_lines = "\n".join(f"- `{script}`" for script in scripts) if scripts else "- No package scripts detected."
        return f"""## 6. Setup and Local Runbook

```bash
{command_block}
```

### Detected Scripts

{script_lines}

### Environment Notes

- Check `.env.example`, README, and configuration files before running.
- Never commit `.env` or API keys.
- If the repository uses external services, start with mocked or local development modes before touching production credentials."""

    def _testing(self) -> str:
        structure = self.analysis.get("structure", {})
        tests = structure.get("test_files", [])
        risks = self.analysis.get("risks", [])
        test_lines = "\n".join(f"- `{test}`" for test in tests[:12]) if tests else "- No obvious tests found in the scanned files."
        risk_lines = "\n".join(f"- {risk}" for risk in risks) if risks else "- No major scan risks detected."
        return f"""## 7. Testing and Risk Areas

### Detected Tests

{test_lines}

### Risks and Gaps

{risk_lines}"""

    def _start_here(self) -> str:
        key_files = self.analysis.get("key_files", [])[:6]
        reading = "\n".join(f"{idx}. `{item['path']}` - {item['purpose']}" for idx, item in enumerate(key_files, 1))
        if not reading:
            reading = "1. README or primary entry point\n2. Configuration files\n3. Source directories\n4. Tests"

        return f"""## 8. Start Here Guide

### First 30 Minutes

{reading}

### First Half Day

1. Run the setup commands.
2. Open the detected entry point and trace one request or execution path.
3. Run the test suite or the closest available verification command.
4. Make a tiny documentation or test change to validate the workflow.

### First Contribution Ideas

- Improve README setup clarity.
- Add or update tests around a small module.
- Document an unclear configuration option.
- Fix a small issue in a low-risk utility or route."""

    def _role_specific(self) -> str:
        structure = self.analysis.get("structure", {})
        tech = self.analysis.get("tech_stack", {})
        if self.role == "manager":
            return f"""## 9. Manager View

- Team onboarding complexity: {self._complexity_label(structure.get('total_files', 0))}
- Main technologies to staff for: {self._join(tech.get('languages', []))}
- Delivery risk areas: tests, environment setup, and ownership of key directories.
- Review focus: confirm setup docs, CI reliability, and whether key modules have owners.

### Manager Questions to Ask

1. Who owns each top-level directory?
2. Which parts are most likely to block a new hire?
3. Are tests fast and reliable enough for first-week contributions?
4. What production services are required for local development?"""

        if self.role == "architect":
            return f"""## 9. Architect View

- Architectural surface: {self._join_code(structure.get('directories', []))}
- Runtime entry points: {self._join_code(structure.get('entry_points', []))}
- Configuration surface: {self._join_code(structure.get('config_files', []))}

### Architecture Review Prompts

1. Validate whether directory boundaries match runtime boundaries.
2. Check whether configuration is centralized and environment-safe.
3. Trace one end-to-end flow from entry point to data or external service.
4. Identify modules that would need isolation before scaling the system."""

        return f"""## 9. Engineer View

- Read entry points first: {self._join_code(structure.get('entry_points', []))}
- Keep config files open while running locally: {self._join_code(structure.get('config_files', []))}
- Use tests as executable documentation: {self._join_code(structure.get('test_files', [])[:8])}

### Engineer Checklist

1. Install dependencies and run the app locally.
2. Run tests before editing.
3. Trace one core flow in the source.
4. Make a small first PR with tests or documentation.
5. Ask SmartOnboard Q&A about unclear files."""

    def _bob_reuse(self) -> str:
        return """## 10. SmartOnboard Bob Mode and Skill

SmartOnboard includes reusable Bob assets for running this workflow inside Bob IDE:

- `.bob/modes/onboarding-guide-generator.yaml`
- `.bob/skills/onboarding-guide.md`

Use these assets with the target repository when you want Bob's full repo context, context mentions such as `@file` and `@folder`, and literate code explanations. This web app produces the shareable guide; the Bob assets make the workflow reusable for teams."""

    @staticmethod
    def _first_readme_paragraph(readme: str) -> str:
        for block in readme.split("\n\n"):
            lines = []
            for line in block.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith("!["):
                    continue
                if "img.shields.io" in stripped or "badge/" in stripped:
                    continue
                markdown_links = re.findall(r"\[[^\]]+\]\([^)]+\)", stripped)
                if len(markdown_links) >= 2 and len(re.sub(r"\[[^\]]+\]\([^)]+\)", "", stripped).strip()) < 20:
                    continue
                lines.append(stripped)
            cleaned = " ".join(lines).strip()
            cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
            cleaned = re.sub(r"[#*_>`]", "", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if len(cleaned) > 60:
                return cleaned[:700]
        return ""

    @staticmethod
    def _summarize_snippet(path: str, text: str) -> str:
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        imports = [line for line in lines if line.lstrip().startswith(("import ", "from ", "const ", "require("))][:5]
        definitions = [
            line.strip()
            for line in lines
            if line.lstrip().startswith(("def ", "class ", "function ", "export ", "async function "))
        ][:6]
        parts = [f"`{path}` is part of the repository's critical surface."]
        if imports:
            parts.append("It pulls in: " + ", ".join(f"`{item[:90]}`" for item in imports) + ".")
        if definitions:
            parts.append("Important definitions found: " + ", ".join(f"`{item[:90]}`" for item in definitions) + ".")
        if len(lines) < 8:
            parts.append("The file is short, so read it in full.")
        return " ".join(parts)

    @staticmethod
    def _join(items: Iterable[Any], fallback: str = "Not detected") -> str:
        values = [str(item) for item in items if item]
        return ", ".join(values) if values else fallback

    @staticmethod
    def _join_code(items: Iterable[Any], fallback: str = "Not detected") -> str:
        values = [f"`{item}`" for item in items if item]
        return ", ".join(values) if values else fallback

    @staticmethod
    def _complexity_label(file_count: int) -> str:
        if file_count < 75:
            return "low to moderate"
        if file_count < 250:
            return "moderate"
        return "high"

    @staticmethod
    def _mermaid_label(value: Any) -> str:
        return str(value).replace("[", "(").replace("]", ")").replace('"', "'")
