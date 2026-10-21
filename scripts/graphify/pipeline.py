"""Deterministic stages of the graphify pipeline.

The stock skill drives these through bash heredocs, which do not survive
PowerShell quoting. Same library calls, one entrypoint:

    python scripts/graphify/pipeline.py <stage>

Stages: detect, ast, cache, merge, build, health, labels, html, finalize, clean

The only stage the host agent still owns is LLM semantic extraction: `cache`
emits graphify-out/.graphify_chunks.json, one subagent per chunk writes
graphify-out/.graphify_chunk_NN.json, then `merge` collects them.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("graphify-out")
SPEC = Path(
    os.environ.get(
        "GRAPHIFY_SPEC",
        Path.home() / ".config/opencode/skills/graphify/references/extraction-spec.md",
    )
)
CHUNK_SIZE = 22  # subagent context ceiling; images get their own chunk


def _root() -> Path:
    return Path.cwd().resolve()


def _read(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _write(name: str, data: dict) -> None:
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def detect(root: Path) -> None:
    from graphify.detect import detect as _detect

    result = _detect(root)
    _write(".graphify_detect.json", result)
    print(f"Corpus: {result['total_files']} files · ~{result.get('total_words', 0):,} words")
    for cat, files in sorted(result.get("files", {}).items()):
        if files:
            print(f"  {cat}: {len(files)}")
    skipped = result.get("skipped_sensitive") or []
    if skipped:
        print(f"  skipped_sensitive: {len(skipped)} -> {', '.join(skipped)}")
    words, files_n = result.get("total_words", 0), result["total_files"]
    if words > 2_000_000 or files_n > 500:
        print(f"LARGE CORPUS: {files_n} files / {words:,} words. Narrow to a subfolder or pass --no-cluster.")
    (OUT / ".graphify_root").write_text(str(root), encoding="utf-8")


def ast(root: Path) -> None:
    from graphify.extract import collect_files, extract

    code: list[Path] = []
    for f in _read(".graphify_detect.json").get("files", {}).get("code", []):
        code.extend(collect_files(Path(f)) if Path(f).is_dir() else [Path(f)])
    if not code:
        _write(".graphify_ast.json", {"nodes": [], "edges": [], "input_tokens": 0, "output_tokens": 0})
        print("AST: no code files")
        return
    result = extract(code, cache_root=root)
    _write(".graphify_ast.json", result)
    print(f"AST: {len(result['nodes'])} nodes, {len(result['edges'])} edges")


def _chunks(files: list[str], root: Path) -> list[list[str]]:
    """One chunk per image, the rest grouped by directory in batches of CHUNK_SIZE."""
    images, prose = [], []
    for f in files:
        (images if Path(f).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"} else prose).append(f)
    out = [[f] for f in images]
    batch: list[str] = []
    for f in sorted(prose, key=lambda p: (str(Path(p).parent), p)):
        batch.append(f)
        if len(batch) == CHUNK_SIZE:
            out.append(batch)
            batch = []
    if batch:
        out.append(batch)
    return out


def cache(root: Path) -> None:
    from graphify.cache import check_semantic_cache

    detect_json = _read(".graphify_detect.json")
    files = [f for cat in ("document", "paper", "image") for f in detect_json["files"].get(cat, [])]
    spec = str(SPEC.resolve()) if SPEC.exists() else str(SPEC)
    cn, ce, ch, uncached = check_semantic_cache(files, root=str(root), prompt_file=spec)
    if cn or ce or ch:
        _write(".graphify_cached.json", {"nodes": cn, "edges": ce, "hyperedges": ch})
    else:
        (OUT / ".graphify_cached.json").unlink(missing_ok=True)
    (OUT / ".graphify_uncached.txt").write_text("\n".join(uncached), encoding="utf-8")
    print(f"Cache: {len(files) - len(uncached)} hit, {len(uncached)} need extraction")
    chunks = _chunks(uncached, root)
    _write(".graphify_chunks.json", chunks)
    for i, c in enumerate(chunks, 1):
        print(f"  chunk {i}/{len(chunks)}: {len(c)} files -> {OUT / f'.graphify_chunk_{i:02d}.json'}")
    if uncached:
        print(f"Semantic extraction: {len(uncached)} files -> {len(chunks)} subagent(s)")


def merge(root: Path) -> None:
    from graphify.cache import save_semantic_cache

    chunks = sorted(glob.glob(str(OUT / ".graphify_chunk_*.json")))
    if not chunks:
        print("no chunk files — skipping semantic merge")
    nodes: list[dict] = []
    edges: list[dict] = []
    hyper: list[dict] = []
    for c in chunks:
        try:
            d = json.loads(Path(c).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"WARNING: {Path(c).name} unreadable ({e}) — skipped")
            continue
        if not d.get("nodes") and not d.get("edges"):
            print(f"WARNING: {Path(c).name} empty — subagent may have failed")
            continue
        nodes += d.get("nodes", [])
        edges += d.get("edges", [])
        hyper += d.get("hyperedges", [])
    _write(".graphify_semantic_new.json", {"nodes": nodes, "edges": edges, "hyperedges": hyper, "input_tokens": 0, "output_tokens": 0})

    uncached = [ln for ln in (OUT / ".graphify_uncached.txt").read_text(encoding="utf-8").splitlines() if ln]
    spec = str(SPEC.resolve()) if SPEC.exists() else str(SPEC)
    if nodes:
        saved = save_semantic_cache(nodes, edges, hyper, root=str(root), allowed_source_files=uncached, prompt_file=spec)
        print(f"cached {saved} files")

    cached = _read(".graphify_cached.json") if (OUT / ".graphify_cached.json").exists() else {"nodes": [], "edges": [], "hyperedges": []}
    seen, deduped = set(), []
    for n in cached["nodes"] + nodes:
        if n["id"] not in seen:
            seen.add(n["id"])
            deduped.append(n)
    _write(".graphify_semantic.json", {
        "nodes": deduped,
        "edges": cached["edges"] + edges,
        "hyperedges": cached.get("hyperedges", []) + hyper,
        "input_tokens": 0,
        "output_tokens": 0,
    })
    print(f"semantic: {len(deduped)} nodes, {len(cached['edges']) + len(edges)} edges ({len(cached['nodes'])} cached)")


def _report(G, communities, cohesion, labels, analysis, detection, tokens, root) -> None:
    from graphify.analyze import suggest_questions
    from graphify.report import generate

    questions = suggest_questions(G, communities, labels)
    (OUT / "GRAPH_REPORT.md").write_text(
        generate(G, communities, cohesion, labels, analysis["gods"], analysis["surprises"], detection, tokens, str(root), suggested_questions=questions),
        encoding="utf-8",
    )


def build(root: Path, force: bool) -> None:
    from graphify.analyze import god_nodes, surprising_connections
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.export import to_json

    extraction = _read(".graphify_extract.json") if (OUT / ".graphify_extract.json").exists() else {}
    if not extraction:
        ast_json = _read(".graphify_ast.json")
        sem = _read(".graphify_semantic.json") if (OUT / ".graphify_semantic.json").exists() else {"nodes": [], "edges": [], "hyperedges": []}
        seen, nodes = {n["id"] for n in ast_json["nodes"]}, list(ast_json["nodes"])
        nodes += [n for n in sem["nodes"] if n["id"] not in seen and not seen.add(n["id"])]
        extraction = {"nodes": nodes, "edges": ast_json["edges"] + sem["edges"], "hyperedges": sem.get("hyperedges", []), "input_tokens": 0, "output_tokens": 0}
        _write(".graphify_extract.json", extraction)

    G = build_from_json(extraction, root=str(root), directed=False)
    if G.number_of_nodes() == 0:
        print("ERROR: empty graph — all files skipped or extraction failed")
        raise SystemExit(1)
    communities = cluster(G)
    cohesion = score_all(G, communities)
    analysis = {
        "communities": {str(k): v for k, v in communities.items()},
        "cohesion": {str(k): v for k, v in cohesion.items()},
        "gods": god_nodes(G),
        "surprises": surprising_connections(G, communities),
    }
    labels = {int(k): v for k, v in json.loads((OUT / ".graphify_labels.json").read_text(encoding="utf-8")).items()} if (OUT / ".graphify_labels.json").exists() else {c: f"Community {c}" for c in communities}
    if not to_json(G, communities, str(OUT / "graph.json"), force=force, community_labels=labels):
        print("ERROR: refused to shrink graph.json (#479). Pass --force if the shrink is intentional.")
        raise SystemExit(1)
    _write(".graphify_analysis.json", analysis)
    _report(G, communities, cohesion, labels, analysis, _read(".graphify_detect.json"), {"input": extraction.get("input_tokens", 0), "output": extraction.get("output_tokens", 0)}, root)
    print(f"graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities")


def labels(root: Path, mapping: str) -> None:
    from graphify.build import build_from_json
    from graphify.cluster import score_all
    from graphify.export import to_json

    mapping_path = OUT / "labels-draft.json"
    # Accept a path or inline JSON: PowerShell eats inline double quotes.
    if mapping and Path(mapping).is_file():
        mapping = Path(mapping).read_text(encoding="utf-8")
    elif mapping is None and mapping_path.is_file():
        mapping = mapping_path.read_text(encoding="utf-8")
    if not mapping:
        print("no labels to apply — write graphify-out/labels-draft.json or pass --mapping <file>")
        return
    new = json.loads(mapping)
    path = OUT / ".graphify_labels.json"
    labels_map = {int(k): v for k, v in new.items()}
    path.write_text(json.dumps({str(k): v for k, v in labels_map.items()}, ensure_ascii=False), encoding="utf-8")
    extraction = _read(".graphify_extract.json")
    analysis = _read(".graphify_analysis.json")
    G = build_from_json(extraction, root=str(root), directed=False)
    communities = {int(k): v for k, v in analysis["communities"].items()}
    cohesion = {int(k): v for k, v in analysis["cohesion"].items()}
    if not to_json(G, communities, str(OUT / "graph.json"), community_labels=labels_map):
        print("ERROR: refused to shrink graph.json (#479)")
        raise SystemExit(1)
    _report(G, communities, cohesion, labels_map, analysis, _read(".graphify_detect.json"), {"input": extraction.get("input_tokens", 0), "output": extraction.get("output_tokens", 0)}, root)
    print(f"labelled {len(labels_map)} communities")


def health(root: Path) -> None:
    from graphify.diagnostics import diagnose_extraction, format_diagnostic_report

    summary = diagnose_extraction(_read(".graphify_extract.json"), directed=False, root=str(root))
    print(format_diagnostic_report(summary))
    flags = [
        f"{summary[k]} {label}"
        for k, label in (
            ("dangling_endpoint_edges", "dangling-endpoint edges"),
            ("missing_endpoint_edges", "missing-endpoint edges"),
            ("self_loop_edges", "self-loop edges"),
            ("directed_same_endpoint_collapsed_edges", "collapsed (directed) edges"),
            ("undirected_same_endpoint_collapsed_edges", "collapsed (undirected) edges"),
        )
        if summary.get(k, 0)
    ]
    print("GRAPH HEALTH WARNING: " + "; ".join(flags) + " — graph may be incomplete." if flags else "Graph health: OK")


def html() -> None:
    r = subprocess.run([sys.executable, "-m", "graphify", "export", "html"], capture_output=True, text=True)
    print((r.stdout or r.stderr).strip() or "html export failed")


def finalize(root: Path) -> None:
    from graphify.cli import _stamped_manifest_files
    from graphify.detect import save_manifest

    detect_json = _read(".graphify_detect.json")
    extract_json = _read(".graphify_extract.json")
    corpus = detect_json.get("all_files") or detect_json["files"]
    files = _stamped_manifest_files(corpus, extract_json, root)
    semantic = {f for t in ("document", "paper", "image") for f in detect_json["files"].get(t, [])}
    stamped = {f for fl in files.values() for f in fl}
    save_manifest(files, root=str(root), scan_corpus={f for fl in corpus.values() for f in fl}, clear_semantic=semantic - stamped or None)

    cost_path = OUT / "cost.json"
    cost = json.loads(cost_path.read_text(encoding="utf-8")) if cost_path.exists() else {"runs": [], "total_input_tokens": 0, "total_output_tokens": 0}
    i, o = extract_json.get("input_tokens", 0), extract_json.get("output_tokens", 0)
    cost["runs"].append({"date": datetime.now(timezone.utc).isoformat(), "input_tokens": i, "output_tokens": o, "files": detect_json.get("total_files", 0)})
    cost["total_input_tokens"] += i
    cost["total_output_tokens"] += o
    cost_path.write_text(json.dumps(cost, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"this run: {i:,} in / {o:,} out · all time: {cost['total_input_tokens']:,} in / {cost['total_output_tokens']:,} out ({len(cost['runs'])} runs)")
    clean()


TEMP = (
    ".graphify_detect.json", ".graphify_extract.json", ".graphify_ast.json",
    ".graphify_semantic.json", ".graphify_semantic_new.json", ".graphify_cached.json",
    ".graphify_analysis.json", ".graphify_uncached.txt", ".graphify_chunks.json", ".needs_update",
)


def clean() -> None:
    gone = 0
    for p in [OUT / n for n in TEMP] + [Path(x) for x in glob.glob(str(OUT / ".graphify_chunk_*.json"))]:
        if p.is_file():
            p.unlink()
            gone += 1
    print(f"cleaned {gone} temp files")


STAGES = {
    "detect": lambda a: detect(_root()),
    "ast": lambda a: ast(_root()),
    "cache": lambda a: cache(_root()),
    "merge": lambda a: merge(_root()),
    "build": lambda a: build(_root(), a.force),
    "health": lambda a: health(_root()),
    "labels": lambda a: labels(_root(), a.mapping),
    "html": lambda a: html(),
    "finalize": lambda a: finalize(_root()),
    "clean": lambda a: clean(),
}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=STAGES)
    ap.add_argument("--root", default=None, help="scan root (default: cwd)")
    ap.add_argument("--force", action="store_true", help="allow graph.json to shrink (#479)")
    ap.add_argument("--mapping", default=None, help="labels stage: JSON file path (default: graphify-out/labels-draft.json)")
    args = ap.parse_args()
    if args.root:
        os.chdir(args.root)
    STAGES[args.stage](args)
