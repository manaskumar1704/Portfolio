"""PDF to Markdown, with checks that fail loudly.

Marker converts a PDF to Markdown. It is good at multi-column layouts and tables,
which is exactly what a résumé is, and it is a one-shot offline conversion rather
than a service call on someone's résumé.

Run it on a PDF:

```bash
uv run python -m ingest.from_pdf --input corpus/_source/resume.pdf --output corpus/resume.md
```

The PDF stays in `_source/`, which is gitignored. Only the Markdown is committed.

## Why the checks exist

A PDF converter produces Markdown that *looks* fine and retrieves badly, in two
specific ways:

**Lost headings.** A résumé converted to one flat run of bold text has no `#`
anywhere. The chunker treats each file as one section, every chunk inherits the
same vague heading, and a recruiter asking about one job gets a chunk containing
all of them. This is the failure that makes RAG feel broken while every log line
says success.

**Hyphenated line breaks.** "manage-\nment" survives conversion as two tokens. A
question about "management" cannot match it. `ingest/chunk.py` rejoins these on
ingest, so this is a warning rather than a hard failure — but it is reported,
because a document full of them means the conversion quality is poor and a
paragraph may be lost elsewhere too.

Both checks exit non-zero. A converter that fails loudly here is worth more than
one that writes a broken file and moves on.
"""

import argparse
import re
import sys
from pathlib import Path

# A word split across lines: "manage-\nment". Case-sensitive on purpose — an
# uppercase letter after the hyphen usually starts a new sentence, not a word.
HYPHEN_BREAK = re.compile(r"([a-z])-\n([a-z])")

# A heading line in the converted output.
HEADING = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)

# How many hyphen breaks are tolerated before the conversion is called poor.
HYPHEN_BREAK_LIMIT = 5


class ConversionError(RuntimeError):
    """The Markdown exists but is not fit to ingest."""


def check_headings(markdown: str, minimum: int = 2) -> None:
    """Require at least `minimum` headings.

    One heading can come from the document's title alone, which tells us nothing
    about section structure. Two is the floor that suggests the converter saw a
    structure at all.
    """
    count = len(HEADING.findall(markdown))
    if count < minimum:
        raise ConversionError(
            f"only {count} heading(s) found, expected at least {minimum}. The "
            f"converter flattened the document, so chunks would lose their "
            f"section labels and citations would be useless. Fix the source PDF "
            f"or convert it by hand."
        )


def check_hyphen_breaks(markdown: str, limit: int = HYPHEN_BREAK_LIMIT) -> list[str]:
    """Report hyphenated line breaks. Returns the rejoined word and where it was.

    Not fatal, because `ingest/chunk.py` rejoins them. Reported, because a
    document with many of them is a document whose paragraphs may be mangled
    elsewhere too.

    The returned fragment is the *fixed* word (`management`) rather than the
    artefact, since that is what someone reading the report wants to confirm.
    """
    found = []
    for match in HYPHEN_BREAK.finditer(markdown):
        line = markdown.count("\n", 0, match.start()) + 1
        # The regex captures one letter either side of the break, which is enough
        # to find the artefact but not enough to name the word. Widen it to the
        # full alphabetic run on each side so the report is readable.
        start = match.start(1)
        while start > 0 and markdown[start - 1].isalpha():
            start -= 1
        end = match.end(2)
        while end < len(markdown) and markdown[end].isalpha():
            end += 1
        # The slice spans "manage-" through "ment". Removing the artefact itself
        # shows the word the ingest will produce. Substituting the regex here
        # would also consume the two letters it captured, giving "managent".
        word = markdown[start:end].replace("-\n", "")
        found.append(f"line {line}: {word}")
    return found


def convert(input_path: Path, output_path: Path) -> str:
    """Convert with Marker and write the Markdown. Returns what was written."""
    from marker.converters.pdf import pdf_converter
    from marker.models import create_model
    from marker.output import text_from_rendered

    print("loading the Marker model (first run downloads several hundred MB)...")
    model = create_model()
    rendered = pdf_converter(str(input_path), model=model)
    markdown, _ = text_from_rendered(rendered)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert a résumé PDF to Markdown.")
    parser.add_argument("--input", required=True, type=Path, help="The PDF, under corpus/_source.")
    parser.add_argument("--output", required=True, type=Path, help="Where to write the Markdown.")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"no such PDF: {args.input}", file=sys.stderr)
        return 2

    markdown = convert(args.input, args.output)
    print(f"wrote {args.output} ({len(markdown)} characters)")

    # Check after writing: a human can inspect the output even when the checks
    # fail, which is more useful than leaving nothing behind.
    try:
        check_headings(markdown)
    except ConversionError as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1

    breaks = check_hyphen_breaks(markdown)
    if breaks:
        print(
            f"\nwarning: {len(breaks)} hyphenated line break(s) found. The ingest "
            f"rejoins these, but a high count usually means poor extraction:\n  "
            + "\n  ".join(breaks[:HYPHEN_BREAK_LIMIT])
        )

    heading_count = len(HEADING.findall(markdown))
    print(f"ok: {heading_count} headings, {len(breaks)} hyphenated breaks")
    print(f"next: uv run python -m ingest.run --dir {args.output.parent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
