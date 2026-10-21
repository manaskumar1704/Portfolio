---
description: Build or refresh the code knowledge graph via scripts/graphify/pipeline.py
---

# /graphify

Build the knowledge graph for `$ARGUMENTS` (default `.`). All deterministic work
goes through `scripts/graphify/pipeline.py` — **never** paste the upstream
skill's bash heredocs, they do not survive PowerShell quoting.

```bash
python scripts/graphify/pipeline.py <stage>
```

Run from the repo root. Stages: `detect ast cache merge build health labels html finalize clean`.

## Steps

1. `detect` — read the corpus summary. If it prints `LARGE CORPUS`, compute the
   top 5 first-level subdirectories by file count and ask which one to scan.
   Wait for the answer. If all files sit in the root, proceed and suggest
   `--no-cluster` instead of asking.
2. `ast` — deterministic structural extraction for code files.
3. `cache` — reads the extraction cache and writes
   `graphify-out/.graphify_chunks.json`, a list of file groups still needing
   semantic extraction. It prints the chunk plan.
4. If `chunks` is non-empty: dispatch **one `general` subagent per chunk, all in
   a single message**. Each subagent gets this prompt with `FILES` replaced by
   its chunk and `NN`/`TOTAL` by its 1-based index and the chunk count:

   > You are a graphify extraction subagent. Read the files listed and extract a
   > knowledge graph fragment. Output ONLY valid JSON, no markdown fences, no
   > preamble.
   >
   > Files (chunk NN of TOTAL):
   > FILES
   >
   > Follow the extraction spec at
   > `~/.config/opencode/skills/graphify/references/extraction-spec.md` — read it
   > first and obey it exactly (node-ID format, confidence rubric, source_file
   > verbatim rule, hyperedge rules).
   >
   > Write the JSON with the Write tool to
   > `graphify-out/.graphify_chunk_NN.json` (zero-padded to two digits).

   A subagent that returns JSON but skips the Write tool did not succeed —
   persist its output yourself before continuing.
5. `merge` — collects the chunk files, updates the cache, merges cached + new.
   Warnings about empty/unreadable chunks are expected when a subagent failed;
   report them rather than aborting. Abort only if more than half the chunks
   failed.
6. `build` — merge, cluster, report, export `graph.json`. Pass `--force` **only**
   when the shrink guard trips and the user confirms the shrink is intentional.
7. `health` — surface any `GRAPH HEALTH WARNING` in the final summary. Never
   hide it; never abort on it.
8. Label communities: read `graphify-out/.graphify_analysis.json`, give every
   community key a 2–5 word plain-language name, write the mapping to
   `graphify-out/labels-draft.json`, then run `labels`. Never leave a community
   named `Community N` when real names are available.
9. `html` — writes the interactive graph.
10. `finalize` — saves the manifest for future `graphify update` runs, appends to
    `cost.json`, and cleans temp files.

## Report back

State the absolute `graphify-out/` path and its three outputs (`graph.html`,
`GRAPH_REPORT.md`, `graph.json`). Then paste **only** these sections from
`GRAPH_REPORT.md`: God Nodes, Surprising Connections, Suggested Questions. Add the
token cost line and any graph-health warning.

Finish by offering to trace the single most interesting suggested question — the
one crossing the most community boundaries. On "yes", run
`graphify query "<question>"` and walk the answer node by node.

## Incremental

If `graph.json` already exists and the request is a natural-language question
about the codebase rather than a rebuild, skip steps 1–10 and answer with
`graphify query "<question>"`. A bare path like `/graphify .` always means a
full rebuild.
