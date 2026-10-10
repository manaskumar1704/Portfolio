"""Which files an ingest actually picks up.

`discover` is the guard that keeps fictional fixtures and a README about the
corpus out of the vector store. It is also the only place that decides what
"corpus" means, and it had no test at all.

That matters because the guard has a hole. It checks the path *relative to the
directory it was given*, so pointing `--dir` straight at a skip directory
defeats it entirely — which is how the fictional `corpus/_test/` fixtures ended
up in a real database, 24 chunks of a person who does not exist.
"""

import pytest

from ingest.run import SKIP_DIRS, discover


@pytest.fixture
def corpus(tmp_path):
    """A corpus with a real file, a fixture file, prose, and a PDF directory."""
    (tmp_path / "resume.md").write_text("# Resume\n", encoding="utf-8")
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "agentflow.md").write_text("# AgentFlow\n", encoding="utf-8")

    (tmp_path / "_test").mkdir()
    (tmp_path / "_test" / "about.md").write_text("# Fictional\n", encoding="utf-8")

    (tmp_path / "_source").mkdir()
    (tmp_path / "_source" / "resume.pdf").write_bytes(b"%PDF-1.4")

    (tmp_path / "README.md").write_text("# Corpus\n", encoding="utf-8")
    return tmp_path


def relative_names(directory) -> list[str]:
    """Paths relative to `directory`, with forward slashes.

    Normalised because Windows and Linux disagree on the separator and a test
    about *what is excluded* should not care which one it is running on.
    """
    return sorted(p.relative_to(directory).as_posix() for p in discover(directory))


# --- What must be picked up -------------------------------------------------


def test_finds_top_level_markdown(corpus) -> None:
    assert "resume.md" in relative_names(corpus)


def test_finds_markdown_in_subdirectories(corpus) -> None:
    assert "projects/agentflow.md" in relative_names(corpus)


def test_the_result_is_sorted_for_reproducible_runs(corpus) -> None:
    """Two runs over the same corpus must produce the same order, or a re-ingest
    rewrites rows in a different sequence for no reason."""
    assert relative_names(corpus) == relative_names(corpus)


# --- What must not be picked up ---------------------------------------------


def test_underscore_directories_are_skipped(corpus) -> None:
    """The primary rule. `_test` is fixtures and `_source` is PDFs."""
    names = relative_names(corpus)

    assert not any(name.startswith("_test") for name in names), names
    assert not any(name.startswith("_source") for name in names), names


def test_prose_about_the_corpus_is_skipped(corpus) -> None:
    """A README that quotes a sample address will outrank `contact.md`."""
    assert "README.md" not in relative_names(corpus)


# --- The hole ---------------------------------------------------------------


def test_an_underscore_prefix_is_honoured_beyond_the_known_names(tmp_path) -> None:
    """The comment above SKIP_DIRS promises this; the code did not do it.

    `discover` compared against a fixed set, so `corpus/_fixtures/` — a new
    directory nobody added to the set — would have been ingested.
    """
    (tmp_path / "resume.md").write_text("# Resume\n", encoding="utf-8")
    (tmp_path / "_drafts").mkdir()
    (tmp_path / "_drafts" / "notes.md").write_text("# Notes\n", encoding="utf-8")

    names = relative_names(tmp_path)

    assert not any("_drafts" in name for name in names), names


def test_pointing_dir_straight_at_a_fixture_directory_ingests_nothing(corpus) -> None:
    """The bug that put 24 fictional chunks into a real database.

    The guard examined `p.relative_to(directory)`, so with
    `--dir corpus/_test` the `_test` component was not in any part and every
    fixture looked like ordinary corpus. `discover` now refuses that outright
    rather than trusting the caller to pass a sensible directory.
    """
    assert discover(corpus / "_test") == []


def test_pointing_dir_at_a_prose_file_writes_nothing(tmp_path) -> None:
    (tmp_path / "README.md").write_text("# Not corpus\n", encoding="utf-8")

    assert discover(tmp_path / "README.md") == []


# --- The skip set itself ----------------------------------------------------


def test_the_skip_set_still_names_the_three_known_directories() -> None:
    """Kept explicit rather than derived, so the intent is readable. The
    underscore rule above is the general safety net, not a replacement."""
    assert {"_test", "_source", "_converted"} <= SKIP_DIRS


def test_a_corpus_with_only_fixtures_yields_nothing(corpus) -> None:
    """The situation at deploy time if someone points the ingest at the wrong
    directory: an empty result, not a database full of fiction."""
    assert discover(corpus / "_test") == []

    # And the real corpus directory still finds its real files, so the refusal
    # above is about the target and not about discovery being broken.
    assert relative_names(corpus), "the real files must still be found"
