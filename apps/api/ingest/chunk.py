"""Turning Markdown into chunks.

This is where RAG quality is decided. Everything downstream is a database read.

## The rule

One chunk is one section, split further only if it is too long. A recruiter asking
"what was his role at Acme" wants the whole Acme section with its heading intact,
not three fragments from the middle of paragraphs. So headings are structure, not
decoration: each one opens a chunk and is carried along as the chunk's
`heading` for citation.

## Sizes

800 characters with 100 of overlap. The overlap is not about recall — it is so a
sentence that straddles a split appears whole in at least one chunk. 800 is under
the model's 512-token input limit with room to spare, which means a chunk is never
silently truncated by the tokenizer.

A 400/50 recursive splitter was rejected: on short Markdown it produces fragments
with no heading context, and every citation loses its label.

## What is skipped

Front-matter, fenced code blocks longer than a chunk, and horizontal rules. The
code-block case is a real hazard rather than a style preference — a résumé with a
`yaml` fence would otherwise have its chunk dominated by configuration.
"""

import re
from dataclasses import dataclass

CHUNK_CHARS = 800
CHUNK_OVERLAP = 100

# A heading line: one to six hashes, then text. Six is arbitrary and generous;
# nobody nests deeper in a portfolio document.
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

_FENCE = re.compile(r"^\s*(```|~~~)")

# A word split across a line break by a PDF converter: "manage-\nment".
_HYPHEN_BREAK = re.compile(r"([a-z])-\n([a-z])")

# Front-matter delimiters.
_FRONTMATTER = ("---", "+++")


@dataclass(frozen=True)
class Chunk:
    """One section, ready to embed."""

    content: str
    heading: str
    index: int


def strip_front_matter(text: str) -> str:
    """Remove YAML/TOML front-matter if the file opens with it."""
    lines = text.splitlines()
    if not lines or lines[0].strip() not in _FRONTMATTER:
        return text

    for i in range(1, len(lines)):
        if lines[i].strip() in _FRONTMATTER:
            return "\n".join(lines[i + 1 :])
    return text


def join_hyphen_breaks(text: str) -> str:
    """Rejoin words a PDF converter split across lines.

    "manage-\nment" becomes "management". Left alone, the hyphen makes the token
    unmatchable: a visitor asking about "management" will not retrieve a chunk
    containing "manage- ment", so a sentence can exist in the corpus and be
    unreachable by the question about it.
    """
    return _HYPHEN_BREAK.sub(r"\1\2", text)


def normalise(text: str) -> str:
    """Front-matter out, hyphen breaks rejoined, whitespace collapsed.

    Collapsing runs of blank lines is what makes the chunking stable: three blank
    lines and one blank line should produce the same chunks, and without this they
    do not.
    """
    text = strip_front_matter(text)
    text = join_hyphen_breaks(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_long(text: str, size: int, overlap: int) -> list[str]:
    """Split an over-long section on paragraph, then sentence, then word.

    Paragraph first because a split mid-paragraph reads badly in a citation. The
    word-level fallback is what guarantees termination on a single 5000-character
    line with no punctuation at all.
    """
    if len(text) <= size:
        return [text]

    pieces: list[str] = []
    buffer = ""
    for paragraph in text.split("\n\n"):
        candidate = f"{buffer}\n\n{paragraph}" if buffer else paragraph
        if len(candidate) <= size:
            buffer = candidate
            continue
        if buffer:
            pieces.append(buffer)
            buffer = ""
        if len(paragraph) <= size:
            buffer = paragraph
            continue
        pieces.extend(_split_by_sentence(paragraph, size, overlap))
    if buffer:
        pieces.append(buffer)

    return _add_overlap(pieces, overlap)


def _split_by_sentence(text: str, size: int, overlap: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[str] = []
    buffer = ""
    for sentence in sentences:
        candidate = f"{buffer} {sentence}" if buffer else sentence
        if len(candidate) <= size:
            buffer = candidate
            continue
        if buffer:
            pieces.append(buffer)
            buffer = ""
        if len(sentence) <= size:
            buffer = sentence
            continue
        # A single sentence longer than the chunk. Hard-wrap on words.
        pieces.extend(_split_oversized_word(sentence, size))
    if buffer:
        pieces.append(buffer)
    return pieces


def _split_oversized_word(sentence: str, size: int) -> list[str]:
    """Wrap text whose words are longer than a chunk.

    A base64 blob, a minified asset, or a line with no spaces at all: the
    word-level wrap above cannot make progress on it, because `split()` hands
    back a single token longer than the budget. Cutting mid-token is ugly but
    terminating beats looping forever, and this content is not something anyone
    reads by eye anyway — it is retrieved, not displayed as prose.
    """
    words = sentence.split()
    pieces: list[str] = []
    buffer = ""
    for word in words:
        while len(word) > size:
            # A word longer than the budget is cut to fit. `words[0]` below can
            # then make progress, so the loop always terminates.
            room = size - len(buffer) - 1 if buffer else size
            if room <= 0:
                pieces.append(buffer)
                buffer = ""
                continue
            fragment = word[:room]
            buffer = f"{buffer} {fragment}" if buffer else fragment
            pieces.append(buffer)
            buffer = ""
            word = word[room:]

        candidate = f"{buffer} {word}" if buffer else word
        if len(candidate) <= size:
            buffer = candidate
            continue
        if buffer:
            pieces.append(buffer)
            buffer = word
        else:
            pieces.append(word)
            buffer = ""
    if buffer:
        pieces.append(buffer)
    return pieces


def _add_overlap(pieces: list[str], overlap: int) -> list[str]:
    """Prepend the tail of the previous piece so split sentences stay whole."""
    if overlap <= 0:
        return pieces
    out = [pieces[0]]
    for previous, current in zip(pieces, pieces[1:], strict=False):
        tail = previous[-overlap:]
        # Only at a word boundary, or the overlap starts mid-word and reads as
        # a typo in the retrieved text.
        space = tail.find(" ")
        if space != -1:
            tail = tail[space + 1 :]
        out.append(f"{tail}\n\n{current}" if tail else current)
    return out


def chunk_markdown(text: str, source_heading: str = "") -> list[Chunk]:
    """Split a document into chunks, one per section.

    `source_heading` is the file's own title, used for sections that appear before
    any heading, which is the common case for a file that opens with a paragraph.
    """
    text = normalise(text)
    if not text:
        return []

    sections: list[tuple[str, str]] = []
    heading = source_heading
    buffer: list[str] = []
    in_fence = False

    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            buffer.append(line)
            continue

        match = None if in_fence else _HEADING.match(line)
        if match is None:
            buffer.append(line)
            continue

        body = "\n".join(buffer).strip()
        if body:
            sections.append((heading, body))
        heading = match.group(2).strip()
        buffer = []

    body = "\n".join(buffer).strip()
    if body:
        sections.append((heading, body))

    chunks: list[Chunk] = []
    index = 0
    for section_heading, body in sections:
        for piece in _split_long(body, CHUNK_CHARS, CHUNK_OVERLAP):
            cleaned = piece.strip()
            if not cleaned:
                continue
            # The heading is prepended so the embedded text carries its own
            # context. A chunk that opens mid-document with no heading is much
            # harder to retrieve and impossible to cite usefully.
            chunks.append(
                Chunk(
                    content=f"{section_heading}\n\n{cleaned}" if section_heading else cleaned,
                    heading=section_heading,
                    index=index,
                )
            )
            index += 1

    return chunks


def read_markdown(path) -> str:
    """Read a file as UTF-8, tolerating a BOM.

    UTF-8 with a byte-order mark is what Windows tools produce, and it makes the
    first heading fail to match — which silently drops the document's title from
    every chunk that inherits it.
    """
    return path.read_text(encoding="utf-8-sig")


def chunk_file(path, source_heading: str = "") -> list[Chunk]:
    return chunk_markdown(read_markdown(path), source_heading)
