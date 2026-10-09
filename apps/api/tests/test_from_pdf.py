"""The PDF conversion checks, without running Marker.

Marker is a large model with a large download, so it is never invoked here. What
is worth testing is the logic that decides whether a conversion is usable, because
that is the part that silently accepts a broken file.
"""

import pytest

from ingest.from_pdf import HYPHEN_BREAK_LIMIT, ConversionError, check_headings, check_hyphen_breaks

GOOD = """# Wren Ashby

## Experience

Staff Search Engineer at Lantern Analytics from 2022.

## Projects

Built Harbour, a query plan differ.
"""


def test_good_markdown_passes() -> None:
    check_headings(GOOD)


def test_flat_markdown_is_rejected() -> None:
    """The failure that makes RAG feel broken while every log says success."""
    flat = "**Wren Ashby**\n\nStaff Search Engineer. **Experience**\n\nLed a team.\n"

    with pytest.raises(ConversionError, match="flattened"):
        check_headings(flat)


def test_one_heading_is_not_enough() -> None:
    """A title alone tells us nothing about section structure."""
    with pytest.raises(ConversionError):
        check_headings("# Resume\n\nSome prose.\n")


def test_the_error_explains_the_consequence() -> None:
    """The message is read by whoever has to fix the PDF."""
    with pytest.raises(ConversionError) as exc:
        check_headings("no headings at all")

    message = str(exc.value)
    assert "citation" in message
    assert "hand" in message


def test_hyphen_breaks_are_found() -> None:
    text = "customer manage-\nment and data engi-\nneering."

    breaks = check_hyphen_breaks(text)

    assert len(breaks) == 2
    # The report shows the fixed word and where it was, not the artefact.
    assert "management" in breaks[0]
    assert "line 1" in breaks[0]


def test_real_hyphens_are_not_flagged() -> None:
    assert check_hyphen_breaks("a full-stack engineer\nwell-known") == []


def test_capital_after_hyphen_is_a_sentence_not_a_word() -> None:
    """`-` before a capital starts a new sentence; joining it would be wrong."""
    assert check_hyphen_breaks("the model failed -\nand the retry worked") == []


def test_hyphen_breaks_are_a_warning_not_a_failure() -> None:
    """The ingest rejoins them, so this returns a list rather than raising."""
    assert check_hyphen_breaks("manage-\nment") != []
    # The limit only controls how many are printed.
    assert HYPHEN_BREAK_LIMIT > 0


def test_clean_document_reports_nothing() -> None:
    assert check_hyphen_breaks(GOOD) == []
    check_headings(GOOD)
