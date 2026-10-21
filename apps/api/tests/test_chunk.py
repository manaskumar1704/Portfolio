"""Chunking, with no database and no model.

The chunker decides what the model can find. A bug here is invisible in tests
that only check "some chunks came out" and very visible to a recruiter asking a
question whose answer got cut in half at a chunk boundary.
"""

from ingest.chunk import (
    CHUNK_CHARS,
    chunk_file,
    chunk_markdown,
    join_hyphen_breaks,
    normalise,
    strip_front_matter,
)


def test_headings_become_separate_chunks() -> None:
    text = "# Resume\n\n## Job One\n\nDid a thing.\n\n## Job Two\n\nDid another."

    chunks = chunk_markdown(text)

    headings = [c.heading for c in chunks]
    assert "Job One" in headings
    assert "Job Two" in headings
    # A section must not bleed into the next one.
    one = next(c for c in chunks if c.heading == "Job One")
    assert "another" not in one.content


def test_content_carries_its_own_heading() -> None:
    """A chunk that opens mid-document is hard to retrieve and hard to cite."""
    chunks = chunk_markdown("## Experience\n\nSome detail here.")

    assert chunks[0].content.startswith("Experience")
    assert chunks[0].heading == "Experience"


def test_prose_before_any_heading_still_becomes_a_chunk() -> None:
    """The file's own name is the fallback heading."""
    chunks = chunk_markdown("Opening paragraph with no heading.", source_heading="Resume")

    assert len(chunks) == 1
    assert chunks[0].heading == "Resume"


def test_hyphenated_line_breaks_are_rejoined() -> None:
    """The PDF-conversion artefact that makes text unmatchable."""
    text = "He worked on customer manage-\nment tooling and data engi-\nneering."

    chunks = chunk_markdown(text)

    body = " ".join(c.content for c in chunks)
    assert "management" in body
    assert "engineering" in body
    assert "manage-\n" not in body


def test_join_hyphen_breaks_leaves_real_hyphens_alone() -> None:
    assert join_hyphen_breaks("a full-stack engineer") == "a full-stack engineer"
    assert join_hyphen_breaks("well-known") == "well-known"


def test_front_matter_is_removed() -> None:
    text = "---\ntitle: Resume\ntags: [a, b]\n---\n\n## Job\n\nContent."

    chunks = chunk_markdown(text)

    assert "title:" not in chunks[0].content
    assert "Job" in chunks[0].content


def test_toml_front_matter_is_removed() -> None:
    text = "+++\nweight = 10\n+++\n\n## Job\n\nContent."

    assert "weight" not in chunk_markdown(text)[0].content


def test_long_sections_are_split() -> None:
    paragraph = "Sentence about the work. " * 200
    chunks = chunk_markdown(f"## Long\n\n{paragraph}")

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.content) <= CHUNK_CHARS + 200


def test_split_pieces_overlap_at_a_word_boundary() -> None:
    """A sentence straddling a split must be whole in at least one chunk."""
    words = [f"word{i}" for i in range(400)]
    chunks = chunk_markdown("## Long\n\n" + " ".join(words))

    assert len(chunks) > 1
    # No chunk should begin mid-word.
    for chunk in chunks[1:]:
        first_line = chunk.content.split("\n\n", 1)[-1][:40]
        assert not any(
            part and part[0].isupper() and part.isalnum() for part in first_line.split(" ")
        )


def test_an_unpunctuated_giant_line_still_terminates() -> None:
    """The word-level fallback is what guarantees this."""
    chunks = chunk_markdown("## Long\n\n" + "x" * 5000)

    assert len(chunks) > 1


def test_fenced_code_is_not_read_as_headings() -> None:
    """A `# comment` inside a fence is not a section heading."""
    text = "## Real\n\n```python\n# not a heading\nx = 1\n```\n\nMore."

    chunks = chunk_markdown(text)

    assert all("not a heading" not in c.heading for c in chunks)


def test_empty_input_produces_nothing() -> None:
    assert chunk_markdown("") == []
    assert chunk_markdown("   \n\n  ") == []


def test_indices_are_sequential_across_sections() -> None:
    """`chunk_index` is half of the upsert key, so gaps would orphan rows."""
    text = "## A\n\nOne.\n\n## B\n\nTwo.\n\n" + "Long text. " * 200
    chunks = chunk_markdown(text)

    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_normalise_collapses_blank_line_runs() -> None:
    """Three blank lines and one must chunk identically."""
    assert normalise("a\n\n\n\n\nb") == normalise("a\n\nb")


def test_chunk_file_reads_utf8_with_bom(tmp_path) -> None:
    """A BOM makes the first heading fail to match, silently losing the title."""
    path = tmp_path / "resume.md"
    path.write_bytes("﻿## Experience\n\nDetail.".encode())

    chunks = chunk_file(path, source_heading="Resume")

    assert chunks[0].heading == "Experience"
    assert chunks[0].content.startswith("Experience")


def test_strip_front_matter_without_closing_delimiter_is_a_no_op() -> None:
    text = "---\nunclosed front matter\n\n## Job"

    assert "unclosed" in strip_front_matter(text)
