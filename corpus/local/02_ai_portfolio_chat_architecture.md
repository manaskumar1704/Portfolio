# Project: AI Portfolio Chat & Recruiter Decision Interface

## Overview & Purpose
An interactive, terminal-inspired AI Portfolio and Recruiter Copilot that answers deep technical questions about Manas Kumar's engineering work, evaluates job description (JD) fit in real time, generates tailored resume bullets, and stages approval-gated outreach emails.

## Key Engineering Highlights (XYZ Metrics)
- **Low-Latency Streaming Architecture:** Engineered an asynchronous FastAPI and Server-Sent Events (SSE) backend with Upstash Redis caching, delivering sub-200ms P95 retrieval latency and real-time token streaming.
- **Loosely Coupled Provider Architecture:** Designed clean `CorpusProvider` and `JobTailorProvider` protocol boundaries, allowing the application to run standalone on a local Markdown/pgvector corpus or switch seamlessly via environment configuration to distributed microservices (`ThirdBrain` GraphRAG and `JobFinder` via REST/MCP).
- **Approval-Gated Recruiter Email Pipeline:** Implemented a strict state-machine workflow (`PENDING_APPROVAL` -> `APPROVED` -> `SENT`) integrated with Resend, ensuring zero autonomous email dispatch without explicit cryptographic approval.
- **Hardened Proxy & Abuse Protection:** Built CIDR-validated proxy header parsing (`TRUSTED_PROXY_CIDRS`), salted SHA-256 IP hashing (`IP_HASH_SALT`), and per-IP rate limiting to prevent quota exhaustion and spoofing behind cloud reverse proxies.
