# Wren Ashby — Projects

> **FIXTURE.** Fictional person. None of these repositories exist.

## Harbour

A command-line tool that turns a running PostgreSQL query plan into a diff against
the previous run, so a regression in index choice is visible in review rather than
in production.

Status: completed. Stack: Python, PostgreSQL, Typer.

## Signal Lantern

A retrieval evaluation harness. Given a corpus and a set of questions with known
relevant documents, it reports recall at k and mean reciprocal rank, and writes the
per-question failures out as a readable report.

Status: completed. Stack: Python, numpy, pytest.

## Driftwatch

A service that polls public API endpoints and raises a ticket when a response
shape changes. Written after a partner API silently renamed a field and three
weeks of jobs produced null values before anyone noticed.

Status: running. Stack: Python, httpx, PostgreSQL.