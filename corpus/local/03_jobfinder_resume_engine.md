# Project: JobFinder — Multi-Service JD Parser, Hybrid Matcher & Typst Resume Engine

## Overview & Problem Solved
JobFinder is an automated career pipeline and SaaS backend composed of four sequential, decoupled microservices that eliminate resume keyword mismatches and slow LaTeX compilation without hallucinating candidate skills.

## 4-Service Pipeline Architecture
1. **Service 1 — JD Ingestion & Structured Parser:** Uses FastAPI and Gemini Structured Outputs (`response_schema` with Pydantic v2) to normalize unstructured job descriptions into strict JSON constraints (`must_have_skills`, `nice_to_have_skills`, `min_yoe`, domain tags).
2. **Service 2 — Deterministic + Semantic Hybrid Matcher:** Computes exact set intersections on required skills alongside `pgvector` HNSW cosine similarity and weighted feature scoring against an immutable bank of verified candidate XYZ bullets. Outputs an honest 3-bucket analysis: `Matched Skills`, `Transferable Skills`, and `Missing Gaps`.
3. **Service 3 — Sub-150ms Typst PDF Compiler:** Injects tailored, character-budgeted JSON achievement blocks into a sandboxed `.typ` template and invokes the native Rust `typst` compiler to produce a layout-guaranteed 1-page PDF in 50–120ms (30x faster than LaTeX).
4. **Service 4 — Approval-Gated Outreach Tracker:** Drafts grounded recruiter outreach emails citing verified project metrics and locks them in PostgreSQL (`PENDING_APPROVAL`) until human sign-off.

## Integration & Security
- Exposes both REST endpoints (`/api/v1/jobfinder/tailor`) and Streamable HTTP Model Context Protocol (MCP) tools (`tailor_resume_to_jd`).
- Protects user-supplied LLM keys at rest using `MultiFernet` encryption and isolates Typst compilation inside a `--root` jailed temporary directory.
