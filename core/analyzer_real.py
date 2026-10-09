"""
Repository analysis for SmartOnboard.

This module performs real work:
- validates and clones public GitHub repositories
- scans the checked-out files
- detects languages, frameworks, package managers, entry points, test files
- extracts important snippets used by the guide and chat endpoints
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse


IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "venv",
    ".venv",
    "env",
    "dist",
    "build",
    ".next",
    "target",
    "coverage",
}

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".swift",
    ".kt",
    ".html",
    ".css",
    ".scss",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".sh",
    ".ps1",
    ".sql",
}

LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++",
    ".hpp": "C++",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
}


class RepositoryAnalyzer:
    """Clone and analyze a public GitHub repository."""

    def __init__(self, repo_url: str, max_files: int = 500):
        self.repo_url = self._normalize_url(repo_url)
        self.max_files = max_files
        self.repo_path: Optional[str] = None
        parsed = urlparse(self.repo_url)
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        self.owner = parts[0] if len(parts) >= 2 else ""
        self.repo_name = parts[1].removesuffix(".git") if len(parts) >= 2 else ""

    @staticmethod
    def _normalize_url(repo_url: str) -> str:
        repo_url = (repo_url or "").strip()
        parsed = urlparse(repo_url)
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            raise ValueError("Only public https://github.com/<owner>/<repo> URLs are supported.")
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(parts) < 2:
            raise ValueError("GitHub URL must include owner and repository name.")
        return f"https://github.com/{parts[0]}/{parts[1].removesuffix('.git')}"

    def clone_repository(self, depth: int = 1) -> str:
        temp_dir = tempfile.mkdtemp(prefix="smartonboard_")
        self.repo_path = temp_dir
        cmd = [
            "git",
            "clone",
            "--depth",
            str(depth),
            "--single-branch",
            self.repo_url,
            temp_dir,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
        except FileNotFoundError as exc:
            try:
                return self._download_repository_archive(temp_dir)
            except Exception as download_exc:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise RuntimeError(
                    "Git is not installed on this runtime, and the GitHub ZIP fallback failed. "
                    f"{download_exc}"
                ) from exc
        except subprocess.TimeoutExpired as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError("Repository clone timed out after 180 seconds.") from exc
        except subprocess.CalledProcessError as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            detail = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(f"Failed to clone repository. {detail}") from exc
        return temp_dir

    def _download_repository_archive(self, temp_dir: str) -> str:
        """Download and extract a public GitHub repo when git is unavailable."""
        import requests

        metadata_url = f"https://api.github.com/repos/{self.owner}/{self.repo_name}"
        metadata_response = requests.get(
            metadata_url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "SmartOnboard"},
            timeout=30,
        )
        metadata_response.raise_for_status()
        default_branch = metadata_response.json().get("default_branch") or "main"

        branch_ref = quote(default_branch, safe="/")
        archive_url = f"https://codeload.github.com/{self.owner}/{self.repo_name}/zip/refs/heads/{branch_ref}"
        archive_response = requests.get(
            archive_url,
            headers={"User-Agent": "SmartOnboard"},
            timeout=120,
        )
        archive_response.raise_for_status()

        archive_path = Path(temp_dir) / "repo.zip"
        archive_path.write_bytes(archive_response.content)

        with zipfile.ZipFile(archive_path) as archive:
            self._safe_extract_zip(archive, Path(temp_dir))
        archive_path.unlink(missing_ok=True)

        extracted_roots = [path for path in Path(temp_dir).iterdir() if path.is_dir()]
        if not extracted_roots:
            raise RuntimeError("GitHub archive did not contain a repository directory.")

        extracted_root = extracted_roots[0]
        for item in extracted_root.iterdir():
            shutil.move(str(item), str(Path(temp_dir) / item.name))
        shutil.rmtree(extracted_root, ignore_errors=True)

        self.repo_path = temp_dir
        return temp_dir

    @staticmethod
    def _safe_extract_zip(archive: zipfile.ZipFile, destination: Path) -> None:
        destination = destination.resolve()
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if not str(target).startswith(str(destination)):
                raise RuntimeError("Unsafe path detected in GitHub archive.")
        archive.extractall(destination)

    def cleanup(self) -> None:
        if self.repo_path and os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path, ignore_errors=True)
        self.repo_path = None

    def analyze(self) -> Dict[str, Any]:
        if not self.repo_path:
            raise RuntimeError("Repository must be cloned before analysis.")

        files = self._iter_files()
        extensions = Counter(path.suffix.lower() or "no_extension" for path in files)
        language_counts = self._language_counts(files)
        tech_stack = self.detect_tech_stack(files, language_counts)
        structure = self.analyze_structure(files, extensions)
        readme = self.get_readme_content()
        package_data = self._read_package_data()
        key_files = self.identify_key_files(files)
        snippets = self.extract_snippets(key_files)

        return {
            "repo_url": self.repo_url,
            "repo_name": self.repo_name,
            "owner": self.owner,
            "readme": readme,
            "package_data": package_data,
            "tech_stack": tech_stack,
            "structure": structure,
            "key_files": key_files,
            "snippets": snippets,
            "risks": self._infer_risks(structure, tech_stack),
            "setup": self._infer_setup_commands(package_data, tech_stack),
            "generated_from": "real_repository_scan",
        }

    def _iter_files(self) -> List[Path]:
        root = Path(self.repo_path or "")
        files: List[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in IGNORE_DIRS for part in path.relative_to(root).parts):
                continue
            files.append(path)
            if len(files) >= self.max_files:
                break
        return files

    def _language_counts(self, files: List[Path]) -> Dict[str, int]:
        counts: Counter[str] = Counter()
        for path in files:
            language = LANGUAGE_MAP.get(path.suffix.lower())
            if language:
                counts[language] += 1
        return dict(counts.most_common())

    def detect_tech_stack(
        self, files: Optional[List[Path]] = None, language_counts: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        files = files or self._iter_files()
        root = Path(self.repo_path or "")
        names = {path.name for path in files}
        tech_stack: Dict[str, Any] = {
            "languages": list((language_counts or self._language_counts(files)).keys()),
            "frameworks": [],
            "package_managers": [],
            "build_tools": [],
            "databases": [],
            "testing": [],
            "dependencies": {},
        }

        if "package.json" in names:
            tech_stack["package_managers"].append("npm")
            tech_stack["build_tools"].append("Node.js")
            package_json = self._read_json(root / "package.json")
            deps = {
                **package_json.get("dependencies", {}),
                **package_json.get("devDependencies", {}),
            }
            tech_stack["dependencies"]["package.json"] = deps
            dependency_names = {name.lower() for name in deps}
            framework_map = {
                "react": "React",
                "vue": "Vue",
                "svelte": "Svelte",
                "next": "Next.js",
                "nuxt": "Nuxt",
                "express": "Express",
                "fastify": "Fastify",
                "nestjs": "NestJS",
                "@nestjs/core": "NestJS",
                "angular": "Angular",
                "@angular/core": "Angular",
            }
            test_map = {
                "jest": "Jest",
                "vitest": "Vitest",
                "mocha": "Mocha",
                "playwright": "Playwright",
                "cypress": "Cypress",
            }
            for dep, label in framework_map.items():
                if dep in dependency_names:
                    tech_stack["frameworks"].append(label)
            for dep, label in test_map.items():
                if dep in dependency_names:
                    tech_stack["testing"].append(label)

        if "requirements.txt" in names:
            tech_stack["package_managers"].append("pip")
            requirements = self._read_text(root / "requirements.txt")
            packages = self._parse_requirements(requirements)
            tech_stack["dependencies"]["requirements.txt"] = packages
            lower = "\n".join(packages).lower()
            for token, label in {
                "flask": "Flask",
                "django": "Django",
                "fastapi": "FastAPI",
                "pytest": "pytest",
                "sqlalchemy": "SQLAlchemy",
                "psycopg": "PostgreSQL",
                "pymongo": "MongoDB",
            }.items():
                if token in lower:
                    target = "testing" if label == "pytest" else "frameworks"
                    if label in {"PostgreSQL", "MongoDB"}:
                        target = "databases"
                    tech_stack[target].append(label)

        config_detections = {
            "pyproject.toml": ("pip/poetry", "Python"),
            "Pipfile": ("pipenv", "Python"),
            "poetry.lock": ("poetry", "Python"),
            "yarn.lock": ("yarn", "Node.js"),
            "pnpm-lock.yaml": ("pnpm", "Node.js"),
            "pom.xml": ("Maven", "Java"),
            "build.gradle": ("Gradle", "Java/Kotlin"),
            "go.mod": ("Go modules", "Go"),
            "Cargo.toml": ("Cargo", "Rust"),
            "Gemfile": ("Bundler", "Ruby"),
            "composer.json": ("Composer", "PHP"),
        }
        for filename, (manager, build_tool) in config_detections.items():
            if filename in names:
                tech_stack["package_managers"].append(manager)
                tech_stack["build_tools"].append(build_tool)

        if "Dockerfile" in names:
            tech_stack["build_tools"].append("Docker")
        if "docker-compose.yml" in names or "compose.yaml" in names:
            tech_stack["build_tools"].append("Docker Compose")

        for key in ["frameworks", "package_managers", "build_tools", "databases", "testing"]:
            tech_stack[key] = sorted(set(tech_stack[key]))
        return tech_stack

    def analyze_structure(self, files: Optional[List[Path]] = None, extensions: Optional[Counter] = None) -> Dict[str, Any]:
        files = files or self._iter_files()
        root = Path(self.repo_path or "")
        top_dirs = sorted(
            {
                rel.parts[0]
                for path in files
                for rel in [path.relative_to(root)]
                if len(rel.parts) > 1 and rel.parts[0] not in IGNORE_DIRS
            }
        )
        total_lines = 0
        test_files = []
        config_files = []
        entry_points = []

        for path in files:
            rel = path.relative_to(root).as_posix()
            if self._is_text_file(path):
                total_lines += self._line_count(path)
            if self._is_test_file(path):
                test_files.append(rel)
            if path.name in self._config_names():
                config_files.append(rel)
            if path.name in self._entrypoint_names():
                entry_points.append(rel)

        return {
            "total_files": len(files),
            "scanned_file_limit": self.max_files,
            "total_lines": total_lines,
            "directories": top_dirs,
            "main_directories": top_dirs,
            "file_types": dict((extensions or Counter(path.suffix.lower() or "no_extension" for path in files)).most_common()),
            "entry_points": sorted(entry_points)[:20],
            "test_files": sorted(test_files)[:30],
            "config_files": sorted(config_files)[:30],
        }

    def identify_key_files(self, files: Optional[List[Path]] = None) -> List[Dict[str, Any]]:
        files = files or self._iter_files()
        root = Path(self.repo_path or "")
        ranked: List[Dict[str, Any]] = []
        priority_names = {
            "README.md": ("Project overview and setup guidance", 100),
            "package.json": ("Node dependency and script manifest", 95),
            "requirements.txt": ("Python dependency manifest", 95),
            "pyproject.toml": ("Python project configuration", 90),
            "app.py": ("Common Python application entry point", 85),
            "main.py": ("Common application entry point", 85),
            "index.js": ("Common JavaScript entry point", 85),
            "server.js": ("Common Node server entry point", 85),
            "Dockerfile": ("Container build definition", 80),
            "docker-compose.yml": ("Local service orchestration", 80),
            ".env.example": ("Environment variable template", 78),
        }

        for path in files:
            rel = path.relative_to(root).as_posix()
            score = 0
            purpose = ""
            if path.name in priority_names:
                purpose, score = priority_names[path.name]
            elif self._is_test_file(path):
                purpose, score = "Representative test coverage", 55
            elif any(part in {"src", "source", "app", "core", "lib", "server", "api", "routes"} for part in path.parts):
                purpose, score = "Core source file", 45
            elif path.name.lower().startswith(("config", "settings")):
                purpose, score = "Configuration file", 70

            if score:
                ranked.append(
                    {
                        "path": rel,
                        "name": path.name,
                        "purpose": purpose,
                        "size": path.stat().st_size,
                        "lines": self._line_count(path) if self._is_text_file(path) else 0,
                        "importance": "high" if score >= 80 else "medium",
                        "score": score,
                    }
                )

        ranked.sort(key=lambda item: (-item["score"], item["path"]))
        return ranked[:20]

    def extract_snippets(self, key_files: List[Dict[str, Any]], max_chars: int = 1800) -> Dict[str, str]:
        root = Path(self.repo_path or "")
        snippets: Dict[str, str] = {}
        for item in key_files[:10]:
            path = root / item["path"]
            if not path.exists() or not self._is_text_file(path):
                continue
            text = self._read_text(path)
            snippets[item["path"]] = text[:max_chars]
        return snippets

    def get_readme_content(self) -> str:
        root = Path(self.repo_path or "")
        for name in ["README.md", "README.MD", "readme.md", "README", "readme"]:
            path = root / name
            if path.exists():
                return self._read_text(path)[:8000]
        return ""

    def _read_package_data(self) -> Dict[str, Any]:
        root = Path(self.repo_path or "")
        data: Dict[str, Any] = {}
        package_json = root / "package.json"
        if package_json.exists():
            data["package_json"] = self._read_json(package_json)
        requirements = root / "requirements.txt"
        if requirements.exists():
            data["requirements"] = self._parse_requirements(self._read_text(requirements))
        return data

    def _infer_setup_commands(self, package_data: Dict[str, Any], tech_stack: Dict[str, Any]) -> Dict[str, List[str]]:
        commands: List[str] = [f"git clone {self.repo_url}", f"cd {self.repo_name}"]
        scripts: Dict[str, str] = package_data.get("package_json", {}).get("scripts", {})
        managers = set(tech_stack.get("package_managers", []))

        if "npm" in managers or "yarn" in managers or "pnpm" in managers:
            commands.append("npm install")
            if "dev" in scripts:
                commands.append("npm run dev")
            elif "start" in scripts:
                commands.append("npm start")
            if "test" in scripts:
                commands.append("npm test")
        if "pip" in managers or "pip/poetry" in managers or "Python" in tech_stack.get("languages", []):
            commands.append("python -m venv .venv")
            commands.append(".venv\\Scripts\\activate  # Windows")
            if package_data.get("requirements"):
                commands.append("pip install -r requirements.txt")
            elif "pip/poetry" in managers:
                commands.append("pip install -e .")
            commands.append("python app.py  # adjust to the detected entry point if needed")
        if "Go modules" in managers:
            commands.extend(["go mod download", "go test ./...", "go run ."])
        if "Cargo" in managers:
            commands.extend(["cargo test", "cargo run"])

        return {
            "commands": commands,
            "scripts": [f"npm run {name}" for name in sorted(scripts)] if scripts else [],
        }

    def _infer_risks(self, structure: Dict[str, Any], tech_stack: Dict[str, Any]) -> List[str]:
        risks = []
        if not structure.get("test_files"):
            risks.append("No obvious test files were found in the scanned file set.")
        if not structure.get("entry_points"):
            risks.append("No standard application entry point was detected automatically.")
        if not tech_stack.get("package_managers"):
            risks.append("No package manager manifest was found, so setup may require manual inspection.")
        if structure.get("total_files", 0) >= self.max_files:
            risks.append(f"Analysis reached the configured scan limit of {self.max_files} files.")
        return risks

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    @staticmethod
    def _read_json(path: Path) -> Dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _parse_requirements(content: str) -> List[str]:
        packages = []
        for raw in content.splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                packages.append(line)
        return packages

    @staticmethod
    def _line_count(path: Path) -> int:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                return sum(1 for _ in handle)
        except OSError:
            return 0

    @staticmethod
    def _is_text_file(path: Path) -> bool:
        return path.suffix.lower() in TEXT_EXTENSIONS or path.name in {
            "Dockerfile",
            "Makefile",
            "Procfile",
            ".env.example",
        }

    @staticmethod
    def _is_test_file(path: Path) -> bool:
        rel = path.as_posix().lower()
        return (
            "/test/" in rel
            or "/tests/" in rel
            or path.name.lower().startswith("test_")
            or path.name.lower().endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts", "_test.go"))
        )

    @staticmethod
    def _entrypoint_names() -> set[str]:
        return {
            "app.py",
            "main.py",
            "__main__.py",
            "index.js",
            "index.ts",
            "server.js",
            "server.ts",
            "main.go",
            "main.rs",
            "Application.java",
            "Main.java",
        }

    @staticmethod
    def _config_names() -> set[str]:
        return {
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "Pipfile",
            "pom.xml",
            "go.mod",
            "Cargo.toml",
            "Dockerfile",
            "docker-compose.yml",
            ".env.example",
            "tsconfig.json",
            "vite.config.js",
            "next.config.js",
        }


def summarize_for_question(analysis: Dict[str, Any], question: str) -> str:
    """Create a deterministic answer using the stored real analysis data."""
    q = question.lower()
    tech = analysis.get("tech_stack", {})
    structure = analysis.get("structure", {})
    key_files = analysis.get("key_files", [])
    setup = analysis.get("setup", {})

    if any(word in q for word in ["start", "read first", "first"]):
        files = key_files[:6]
        lines = [f"- `{item['path']}`: {item['purpose']}" for item in files]
        return "Start with these files:\n" + "\n".join(lines)

    if any(word in q for word in ["run", "setup", "install", "test"]):
        commands = setup.get("commands", [])
        scripts = setup.get("scripts", [])
        body = "Detected setup commands:\n" + "\n".join(f"- `{cmd}`" for cmd in commands)
        if scripts:
            body += "\n\nDetected package scripts:\n" + "\n".join(f"- `{script}`" for script in scripts)
        return body

    if any(word in q for word in ["architecture", "design", "flow"]):
        dirs = ", ".join(structure.get("directories", [])[:12]) or "no top-level directories detected"
        entries = ", ".join(structure.get("entry_points", [])[:8]) or "no standard entry point detected"
        return (
            f"The repository appears to be organized around these top-level areas: {dirs}. "
            f"Detected entry points: {entries}. The guide's architecture section maps these into the likely runtime flow."
        )

    if any(word in q for word in ["tech", "stack", "framework", "language"]):
        return (
            f"Languages: {', '.join(tech.get('languages', [])) or 'not detected'}.\n"
            f"Frameworks: {', '.join(tech.get('frameworks', [])) or 'not detected'}.\n"
            f"Package managers: {', '.join(tech.get('package_managers', [])) or 'not detected'}."
        )

    return (
        f"I analyzed `{analysis.get('repo_url')}`: {structure.get('total_files', 0)} files, "
        f"{structure.get('total_lines', 0)} lines, languages "
        f"{', '.join(tech.get('languages', [])) or 'not detected'}. "
        "Ask about setup, architecture, key files, tests, or where to start for a more specific answer."
    )
