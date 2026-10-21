/**
 * The transport. POST, stream, hand frames to a parser.
 *
 * ## Why not EventSource
 *
 * `EventSource` is GET-only and cannot carry a request body. `POST /chat` takes
 * the question as JSON. That settles it.
 *
 * ## Why fetch and not the Next route handler
 *
 * Because the browser calls Render directly.
 *
 * It is not only about a hop. The send route requires the visitor's IP to match
 * the one the draft was written from, and it reads that from `X-Forwarded-For`
 * only when the socket peer is a trusted proxy. Routing through a Next.js route
 * handler inserts Vercel between the browser and Render, so Render sees Vercel's
 * address rather than the visitor's and every approval fails with a 403 that
 * looks like a bug.
 *
 * The cost is CORS, which is a strict allowlist on the API. That is a smaller
 * price than an approve button that never works.
 *
 * ## The response is not JSON
 *
 * It is `text/event-stream`. Reading it as `.json()` hangs until the stream
 * closes and then throws. This reads the body as a byte stream and hands chunks
 * to the parser, which is why the parser is the unit worth testing on its own.
 */

import { apiUrl } from "./config";
import { parseSseFrames } from "./parse-sse";
import type { ChatEvent } from "./types";

/** A raised when the stream itself fails, as opposed to a `busy` or `error` frame. */
export class ChatStreamError extends Error {
  constructor(
    message: string,
    /** The HTTP status, or 0 for a network failure with no response. */
    readonly status: number,
  ) {
    super(message);
    this.name = "ChatStreamError";
  }
}

/** What `/chat` needs beyond the question. */
export type ChatRequest = {
  message: string;
  /** Prior turns, oldest first. Matches `ChatMessage` minus the render fields. */
  history?: { role: "user" | "bot"; text: string }[];
  signal?: AbortSignal;
};

/**
 * POST a question and yield frames as they arrive.
 *
 * Yields every event the parser recognises, including ones this version of the
 * UI ignores, so a backend that adds an event does not break an older frontend.
 */
export async function* streamChat(request: ChatRequest): AsyncGenerator<ChatEvent> {
  const response = await fetch(apiUrl("/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      message: request.message,
      history: request.history ?? [],
    }),
    signal: request.signal,
  });

  if (!response.ok) {
    // The body of a failure is JSON with `detail`, not an SSE stream, so there
    // is nothing to parse. The status is what the caller acts on.
    throw new ChatStreamError(await errorText(response), response.status);
  }

  if (!response.body) {
    throw new ChatStreamError("The response had no body to stream.", 0);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      // `stream: true` so a multi-byte character split across two chunks decodes
      // as one. The default replaces it with U+FFFD, which would corrupt any
      // answer containing an em dash or an accented name — and a recruiter's
      // name is exactly that.
      pending += decoder.decode(value, { stream: true });

      const { events, rest } = parseSseFrames(pending);
      pending = rest;

      for (const event of events) yield event;
    }

    // A server that closes without a final newline still sent a complete last
    // frame. Flush whatever is left rather than dropping it.
    const tail = parseSseFrames(pending + "\n\n");
    for (const event of tail.events) yield event;
  } finally {
    // Releasing the lock lets the connection be torn down promptly when the
    // consumer stops early, which it does on every error and on unmount.
    reader.releaseLock();
  }
}

/**
 * The server's own explanation, when it gives one.
 *
 * Never the raw body: a FastAPI `detail` can be a list of validation objects,
 * and the message is shown to a visitor.
 */
async function errorText(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    const detail = payload?.detail;
    if (typeof detail === "string" && detail) return detail;
  } catch {
    // Not JSON, or no body. The status-based fallback below is better anyway.
  }
  return `The server returned ${response.status}.`;
}

/**
 * Whether the API is awake.
 *
 * Deliberately `/health` and never `/ready`: `/ready` opens a Postgres
 * connection, and calling it on every page load would hold Neon out of
 * scale-to-zero. `/health` answers in about a millisecond from a warm container
 * and takes the cold-start path from a sleeping one, which is exactly what this
 * needs to measure.
 */
export async function pingHealth(
  signal?: AbortSignal,
): Promise<{ ok: boolean; coldStartMs: number }> {
  const started = Date.now();
  try {
    const response = await fetch(apiUrl("/health"), { signal, cache: "no-store" });
    return { ok: response.ok, coldStartMs: Date.now() - started };
  } catch {
    // A refused connection is the answer, not an exception to propagate: a
    // sleeping Render instance does not respond at all, and that is the state
    // the caller is trying to detect.
    return { ok: false, coldStartMs: Date.now() - started };
  }
}