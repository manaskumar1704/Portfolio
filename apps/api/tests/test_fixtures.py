"""The fixture loader's protection is structural, not a runtime guard.

`discover` needs a _guard_ because it takes a caller-chosen `--dir`. The
fixture loader takes no directory argument at all: `fixture_directory` can only
return a path whose leaf is `_test`, and the file list excludes README prose
and underscore directories, which is what kept the fixture README outranking
the corpus the last time this was wired the other way. These tests pin that.
"""

from pathlib import Path

from ingest.fixtures import fixture_directory, list_fixture_files


def test_the_directory_is_always_a_test_leaf() -> None:
    """`CORPUS_DIR` pointing at a real corpus gets the `_test` sibling."""
    directory = fixture_directory(str(Path("somewhere", "corpus")))

    assert directory.name == "_test"


def test_the_checkout_layout_resolves_wherever_the_cwd_is() -> None:
    """The dev `CORPUS_DIR` reads as `corpus`, relative to *some* cwd.

    From `apps/api` — the ingest docs' cwd — it does not exist as written, so
    the fallback resolves it from the repo root, three parents up from the
    fixtures module. Asserting on real fixture files rather than a mock: a
    resolution that points nowhere reads as "no fixture files" in the loader,
    which is precisely the failure I hit before this branch existed.
    """
    directory = fixture_directory("corpus")

    assert directory.name == "_test"
    assert (directory / "about.md").exists()


def test_an_existing_relative_path_is_honoured_as_written(tmp_path: Path) -> None:
    """A path that does exist is used literally, not second-guessed."""
    fixture_dir = tmp_path / "corpus" / "_test"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "about.md").write_text("# About\n", encoding="utf-8")

    # tmp_path is absolute, so `exists()` is true regardless of cwd; what
    # matters here is that an existing path is not re-rooted on top of it.
    directory = fixture_directory(str(fixture_dir))

    assert directory == fixture_dir
    assert list_fixture_files(directory)[0].name == "about.md"


def test_the_file_list_skips_prose_and_underscore_directories(tmp_path: Path) -> None:
    (tmp_path / "about.md").write_text("# About\n\nA fixture.", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Fixture corpus\n", encoding="utf-8")
    subdir = tmp_path / "_drafts"
    subdir.mkdir()
    (subdir / "notes.md").write_text("# Notes\n", encoding="utf-8")

    files = list_fixture_files(tmp_path)

    names = [p.name for p in files]
    assert names == ["about.md"]
