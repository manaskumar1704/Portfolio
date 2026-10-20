/**
 * The parser: a growing buffer of SSE bytes → complete `ChatEvent`s.
 *
 * The one job that matters is split frames. Network chunks land wherever they
 * like — mid-word, mid-JSON, mid-`\n` — so a parser that maps one chunk to one
 * frame works on a laptop and scrambles answers in production. Every call
 * returns the trailing partial frame as `rest`, **unchanged**, for the next
 * chunk to complete.
 *
 * The wire format comes from `app/api/chat.py` `_frame()`:
 *
 *     event: <name>\n
 *     data: <json>\n
 *     \n
 *
 * and the server's snake_case keys become the camelCase `ChatEvent` types here,
 * so nothing downstream has to know which is which.
 *
 * Legal-but-unusual SSE is handled rather than rejected: a frame without
 * `data:`, several `data:` lines (joined with `\n`, per the spec), comment
 * keep-alives (`:`), CRLF re-framing by a proxy, and event names this version
 * does not know — those come back as `{ kind: "unknown" }` so the backend can
 * add events without breaking an older frontend.
 */

import type { ChatEvent } from "./types";

/** Every kind the backend currently emits (see `app/services/chat.py`). */
const KNOWN_KINDS = new Set([
  "delta",
  "tool_call",
  "tool_result",
  "citation",
  "draft",
  "busy",
  "error",
  "done",
]);

export function parseSseFrames(buffer: string): { events: ChatEvent[]; rest: string } {
  const events: ChatEvent[] = [];
  let cursor = 0;

  for (;;) {
    const separator = nextSeparator(buffer, cursor);
    if (separator === null) break;

    const event = parseFrame(buffer.slice(cursor, separator.start));
    if (event !== null) events.push(event);

    // Not `.trim()`ed: `rest` must survive byte-for-byte, because a leading
    // space on the next `data:` line is required by the spec to be exactly
    // one wide.
    cursor = separator.end;
  }

  return { events, rest: buffer.slice(cursor) };
}

/**
 * The earliest frame boundary at or after `from`.
 *
 * Both terminators exist. The server sends `\n\n`; a proxy is entitled to
 * re-frame with `\r\n\r\n`. Searching for both is what makes a CRLF stream
 * parse identically — `\r\n\r\n` contains no `\n\n`, so matching only `\n\n`
 * would leave a stray `\r` glued to every data value.
 */
function nextSeparator(buffer: string, from: number): { start: number; end: number } | null {
  const lf = buffer.indexOf("\n\n", from);
  const crlf = buffer.indexOf("\r\n\r\n", from);

  if (lf === -1 && crlf === -1) return null;
  if (crlf === -1 || (lf !== -1 && lf < crlf)) return { start: lf, end: lf + 2 };
  return { start: crlf, end: crlf + 4 };
}

/** One completed frame → one event, or `null` when the frame carries nothing. */
function parseFrame(text: string): ChatEvent | null {
  let name: string | null = null;
  const dataLines: string[] = [];

  for (const rawLine of text.split("\n")) {
    // A CRLF stream keeps its `\r` on every line, not just the separators.
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;

    if (line.startsWith(":")) continue; // comment keep-alive; no event
    if (line === "") continue; // separator leftovers

    const colon = line.indexOf(":");
    if (colon === -1) continue; // not a field, so not something we emit

    const field = line.slice(0, colon);
    // Exactly one space after the colon is the separator, not data.
    const value = line[colon + 1] === " " ? line.slice(colon + 2) : line.slice(colon + 1);

    if (field === "event") name = value;
    else if (field === "data") dataLines.push(value);
  }

  const kind = name ?? "message"; // the anonymous SSE form; the server never sends it

  // Nothing in the frame — blank lines or a comment-only keep-alive. Emitting
  // here would manufacture events out of whitespace between real frames.
  if (name === null && dataLines.length === 0) return null;

  let data: unknown = undefined;
  if (dataLines.length > 0) {
    try {
      data = JSON.parse(dataLines.join("\n"));
    } catch {
      // A truncated payload from a dropped connection. Skipping it loses one
      // frame; throwing loses every answer already received, so it returns.
      return null;
    }
  }

  if (!KNOWN_KINDS.has(kind)) {
    // `data` stays present with an undefined value when the frame had none —
    // toEqual treats the pair as equal, and the union requires the key.
    return { kind: "unknown", name: kind, data };
  }

  const payload = (data ?? {}) as Record<string, unknown>;
  return mapKnown(kind, payload);
}

/** The snake_case-wire → camelCase-type mapping, for one kind. */
function mapKnown(kind: string, d: Record<string, unknown>): ChatEvent {
  const str = (value: unknown): string => (value as string | undefined) ?? "";
  const num = (value: unknown): number => (value as number | undefined) ?? 0;

  switch (kind) {
    case "delta":
      return { kind: "delta", text: str(d.text) };
    case "tool_call":
      return {
        kind: "tool_call",
        id: str(d.id),
        name: str(d.name),
        arguments: str(d.arguments),
      };
    case "tool_result":
      return {
        kind: "tool_result",
        id: str(d.id),
        name: str(d.name),
        ok: Boolean(d.ok),
        error: (d.error as string | null | undefined) ?? null,
      };
    case "citation":
      return { kind: "citation", sourcePath: str(d.source_path), label: str(d.label) };
    case "draft":
      return {
        kind: "draft",
        id: num(d.id),
        name: str(d.name),
        senderEmail: str(d.sender_email),
        body: str(d.body),
        approvalToken: str(d.approval_token),
        expiresAt: str(d.expires_at),
      };
    case "busy":
      return {
        kind: "busy",
        retryAfterSeconds: num(d.retry_after_seconds),
        message: str(d.message),
      };
    case "error":
      return { kind: "error", message: str(d.message) };
    default: // "done" — the last member of KNOWN_KINDS
      return {
        kind: "done",
        sources: Array.isArray(d.sources) ? d.sources.map(String) : [],
        textLength: num(d.text_length),
        // Strictly true: `undefined` must never read as verified.
        sourcesVerified: d.sources_verified === true,
      };
  }
}
