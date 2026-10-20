"""Groundedness, scored offline by the NLI harness.

`slow`: downloads ~83 MB once (huggingface cache) and runs local inference.
Everything else in the eval suite is CPU-trivial by comparison. Never in the
API image — Node/Python runtime exports of `render.yaml` exclude `evals/**`.
The runner deliberately runs this file by name from the CI evals job only.

## The harness and the measured ceiling

`cross-encoder/nli-distilroberta-base` ships its own int8-quantised ONNX
(`onnx/model_qint8_avx512.onnx`, 82.8 MB, ~170 ms/pair on one core). This is
the exact artifact whose behaviour was measured before deciding the badge
stays dark: against chunk-sized premises, natural-language entailment blurs
into neutral. It is the reason the NLI check belongs to JobFinder's service
later (ADR 0008), and the reason `services/verify.py` is a seam rather than a
wired verifier (ADR 0009).

This file pins what the harness can and cannot do, at the shape level, so the
ceiling is documented behaviorally rather than only in prose:

- a supported paraphrase **entails** ✔ — the easy, unambiguous shape;
- a contradicted date **contradicts** ✔;
- an arithmetic restatement of the same numbers ("moved from 31% to 44%" →
  "improved by 13 points") stays **neutral** — the known blind spot;
- an unrelated fact from the same document stays **neutral** — no domain bias.

If a re-pin changes after a model update, the ceiling moved, and the decisions
log should hear about it again. The label order (contradiction, entailment,
neutral) is the sentence-transformers cross-encoder convention for this model
and was confirmed empirically per pair below.
"""

import numpy as np
import onnxruntime as ort
import pytest
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

pytestmark = [pytest.mark.slow]

# (repo, file). The int8 build the repo ships for AVX-512 hosts; CI runners
# and dev machines have it. `model_qint8_arm64.onnx` is the sibling for Mac.
MODEL_ID = "cross-encoder/nli-distilroberta-base"
ONNX_FILE = "onnx/model_qint8_avx512.onnx"

# The sentence-transformers cross-encoder head: 3 logits in this order.
CONTRADICTION, ENTAILMENT, NEUTRAL = 0, 1, 2

_session: ort.InferenceSession | None = None
_tokenizer: Tokenizer | None = None

# Premises are single sentences lifted from the fixture corpus (resume.md and
# naukri-snapshot.md), not whole chunks: the chunk-sized premise is the blind
# spot being documented, and premise-per-sentence is what a future JobFinder
# verifier would feed the model anyway.
Pair = tuple[str, str, int]

PAIRS: list[Pair] = [
    # supported paraphrases — the entailment shape
    (
        "Reduced p99 search latency from 840 ms to 190 ms.",
        "Search latency was reduced.",
        ENTAILMENT,
    ),
    (
        "Mentors two engineers and runs the on-call rotation.",
        "Wren mentors engineers.",
        ENTAILMENT,
    ),
    (
        "Built the ingestion pipeline for clinical trial records.",
        "There is a pipeline that ingests clinical records.",
        ENTAILMENT,
    ),
    # contradicted fact
    (
        "Joined Cardinal Health Data in 2019.",
        "Wren left Cardinal Health Data in 2018.",
        CONTRADICTION,
    ),
    # the measured blind spot: arithmetic restatement, same document
    (
        "Moved click-through on the top ten results from 31% to 44%.",
        "Click-through improved by 13 percentage points.",
        NEUTRAL,
    ),
    # unrelated-but-same-domain
    ("Mentors two engineers.", "Wren speaks fluent Japanese.", NEUTRAL),
]


def _scores(premise: str, claim: str) -> np.ndarray:
    """Three logits for one premise/claim pair."""
    global _session, _tokenizer

    if _tokenizer is None:
        _tokenizer = Tokenizer.from_file(hf_hub_download(MODEL_ID, "tokenizer.json"))
    if _session is None:
        _session = ort.InferenceSession(
            hf_hub_download(MODEL_ID, ONNX_FILE), providers=["CPUExecutionProvider"]
        )

    encoded = _tokenizer.encode(premise, claim)
    feeds = {
        "input_ids": np.array([encoded.ids], dtype=np.int64),
        "attention_mask": np.array([encoded.attention_mask], dtype=np.int64),
    }
    return _session.run(None, feeds)[0][0]


@pytest.mark.parametrize(("premise", "claim", "expected"), PAIRS)
def test_the_nli_harness_scores_pairs_as_measured(
    premise: str, claim: str, expected: int
) -> None:
    logits = _scores(premise, claim)

    assert int(np.argmax(logits)) == expected, (
        f"{claim!r} vs {premise!r}: expected {expected}, got {logits}"
    )
