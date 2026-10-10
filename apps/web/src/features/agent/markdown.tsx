"use client";

/**
 * Renders an agent answer as Markdown, with the escape hatches closed.
 *
 * The answer is model output. It is influenced by whatever a retrieved corpus
 * chunk or a visitor's question said, which makes it untrusted text with a very
 * convincing delivery mechanism. See `docs/decisions/0007-safe-markdown-rendering.md`.
 *
 * ## Three things are off on purpose
 *
 * **Raw HTML.** No `rehype-raw`. Without it, a `<script>` or `<img onerror=…>`
 * in an answer renders as the literal characters, which is the correct outcome.
 * With it, the same text is markup, and the model will reproduce a payload from
 * a corpus chunk without any intent of its own.
 *
 * **Images.** Overridden to render `alt` text and nothing else. A rendered
 * `<img>` is a GET to an attacker-chosen URL from the visitor's browser, with
 * their IP and their `Referer`. The model emits `![](…)` without thinking about
 * it, so the guard is here rather than in the prompt.
 *
 * **Non-http(s) links.** `urlTransform` drops `javascript:` and `data:` hrefs.
 * react-markdown already defaults to this; the override is so the rule is stated
 * in this repository and tested, rather than inherited from a default that could
 * change.
 *
 * There is no `dangerouslySetInnerHTML` anywhere in this component, and adding
 * one would need its own decision record.
 */

import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Schemes a link may use. Everything else is dropped. */
const SAFE_SCHEMES = new Set(["http:", "https:", "mailto:"]);

export function AgentMarkdown({ text }: { text: string }) {
  return (
    <div className="md">
      <Markdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => (isSafeUrl(url) ? url : "")}
        components={{
          // Rendered as words, never as a request. `children` is the alt text.
          img: ({ alt }) => (alt ? <span className="md-alt">[{alt}]</span> : null),

          // No `target` without `rel`, or the opened page gets a live
          // `window.opener` handle on this one.
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),

          // `p` and `li` are block-level, which puts a browser gap between every
          // paragraph inside a list item. Tighter is what a terminal-style UI
          // wants.
          p: ({ children }) => <p className="md-p">{children}</p>,

          // The model marks tools it is about to call. Showing which one is more
          // informative than a spinner, and it is honest about the retrieval.
          table: ({ children }) => (
            <div className="md-scroll">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {text}
      </Markdown>
    </div>
  );
}

/**
 * Whether a URL is safe to put in an `href`.
 *
 * Relative URLs are allowed: the answer may link to a page on this site. The
 * scheme check is on absolute URLs, where `javascript:` is the threat.
 */
function isSafeUrl(url: string): boolean {
  // A protocol-relative URL (`//evil.test`) inherits the current scheme, which is
  // https here, so it is fine. What is not fine is an explicit bad scheme.
  const scheme = /^([a-z][a-z0-9+.-]*):/i.exec(url.trim());

  if (!scheme) return true;

  return SAFE_SCHEMES.has(`${scheme[1].toLowerCase()}:`);
}