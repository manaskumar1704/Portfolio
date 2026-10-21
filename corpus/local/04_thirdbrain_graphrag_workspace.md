# Project: ThirdBrain — 3D Hybrid GraphRAG & Multi-LLM Workspace

## Overview & Problem Solved
Standard vector-only RAG fails on multi-hop architectural queries and keyword-specific technical terms. ThirdBrain is a standalone Hybrid GraphRAG knowledge workspace and Multi-LLM comparison engine with an interactive 3D spatial citation graph.

## Core Retrieval & Ingestion Architecture
- **Zero-LLM-Cost Graph Ingestion:** Splits technical documents via structure-aware Markdown chunking, extracts typed entities (`PROJECT`, `TECH_STACK`, `METRIC`) locally in milliseconds using **GLiNER** (zero-shot NER), and computes 3D spatial coordinates using **UMAP** (`n_components=3`).
- **3-Way Hybrid Retrieval with Reciprocal Rank Fusion (RRF):** Executes a unified PostgreSQL CTE combining:
  1. **Semantic Search:** `pgvector` HNSW cosine distance (`vector_cosine_ops`).
  2. **Lexical Search:** PostgreSQL Full-Text Search (`tsvector` / `ts_rank` BM25 equivalent) for exact technical identifiers (e.g., `MultiFernet`, `Alembic`, `HNSW`).
  3. **Graph Traversal:** 1-hop entity-relationship expansion across `graph_entities` and `graph_edges`.
  Results are fused deterministically via Reciprocal Rank Fusion ($RRF\_Score = \sum \frac{1}{60 + rank_i}$) in under 50ms.
- **Interactive 3D Citation Canvas:** Built with Next.js and **React Three Fiber (Three.js)**. Streaming SSE responses emit active `chunk_id` and `node_id` payloads that illuminate corresponding knowledge clusters and edges in 3D space.
