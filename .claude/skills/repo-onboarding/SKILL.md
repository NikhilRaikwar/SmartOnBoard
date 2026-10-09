---
name: repo-onboarding
description: Generate comprehensive onboarding guides, architecture maps, and key file rundowns for any codebase.
---

# Codebase Onboarding Guide Skill

## Purpose
Generate comprehensive onboarding guides for any codebase, reducing new developer ramp-up time from weeks to minutes.

## When to Use
- New team member joining a project
- Analyzing an unfamiliar codebase
- Creating architecture documentation for existing projects
- Preparing for code reviews or architecture audits
- Understanding complex legacy systems

## How to Use
1. Ensure access to the target repository directory
2. Specify the target role (Engineer, Manager, or Architect)
3. Use SmartOnboard's read-only inspection tools (`list_files`, `read_file`, `search_code`) to inspect entry points and manifests
4. Synthesize the structured onboarding guide with architecture flows, setup steps, and key files

## Expected Output Sections
1. **Project Overview** - What the project does, detected languages, frameworks, and fast facts
2. **Architecture & Design** - Runtime entry points, module relationships, and Mermaid diagrams
3. **Key File Map** - Top-level critical files with purpose and line counts
4. **Setup & Installation** - Prerequisites, installation commands, and detected package scripts
5. **Testing Strategy** - Test structure, verification commands, and risk areas
6. **First Contribution Guide** - Recommended reading order, first PR ideas, and safe starting points
7. **Role-Specific Insights** - Tailored focus areas for Engineers, Managers, or Architects

## Quality Checklist
- [ ] Every factual claim cites an existing file path
- [ ] Setup instructions are inferred directly from repo manifests (`package.json`, `pyproject.toml`, etc.)
- [ ] Architecture diagram accurately reflects entry points and directory layout
- [ ] Critical files are explained with line numbers and rationale
- [ ] No speculative or invented file paths are included
