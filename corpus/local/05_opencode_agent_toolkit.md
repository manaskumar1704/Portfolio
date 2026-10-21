# Project: OpenCode Agent Toolkit (opencode-toolkit) — CLI, AST Security Gate & Skill Router

## Overview & Problem Solved
Developer coding agents suffer from context-window bloat when loading dozens of global skills and face severe local security risks when executing untrusted community hooks or MCP scripts. `opencode-toolkit` is a TypeScript CLI and Terminal UI (TUI) that manages global agent configurations (`~/.config/opencode`) safely and efficiently.

## Key Capabilities & Engineering Design
- **Deterministic Tree-Sitter AST Security Scanner (`opencode-kit scan`):** Parses `.ts`, `.py`, and `.sh` skill scripts and hooks into Abstract Syntax Trees using `tree-sitter`. Deterministically flags dangerous sinks—such as arbitrary shell execution (`child_process.exec`, `os.system`), `.env` or `~/.ssh` credential reads, and unauthorized outbound network calls—without relying on probabilistic LLM code review.
- **Context-Budget Semantic Skill Router (`opencode-kit route`):** Fingerprints the active repository stack (`pyproject.toml`, `package.json`, `Dockerfile`) and uses local embedding cosine similarity to load only the top-3 relevant skills, reducing prompt token overhead by over 70%.
- **Decision-First `/ideate` Workflow Generator:** Enforces structured engineering habits by prompting the developer to resolve key architectural trade-offs first, recording the decision in an Architecture Decision Record (`ADR`), and generating a phased build checklist.
