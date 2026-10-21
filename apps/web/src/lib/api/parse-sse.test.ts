/**
 * YOU IMPLEMENT THIS FILE. `parse-sse.ts` does not exist yet.
 *
 * The tests below are the specification. They are red until you write it, and
 * they are the only thing in the frontend that is red.
 *
 * ## What the parser has to do
 *
 * Turn a growing string of SSE bytes into complete events, and hand back
 * whatever partial frame is left over so the next chunk can complete it.
 *
 * That "whatever is left over" part is the whole job. Network chunks split
 * wherever they like: a frame boundary can land mid-word, mid-JSON, or mid-`\n`.
 * A parser that assumes one chunk is one frame works on a laptop and produces
 * scrambled answers in production.
 *
 * ## What the server actually sends
 *
 * From `app/api/chat.py`, `_frame()`:
 *
 *     event: <name>\n
 *     data: <json>\n
 *     \n
 *
 * Named events rather than bare `data:` lines, so the frontend can switch on the
 * type and ignore anything it does not recognise.
 *
 * Known event names: `delta`, `tool_call`, `tool_result`, `citation`, `draft`,
 * `busy`, `error`, `done`.
 *
 * ## Signature the tests import
 *
 *     parseSseFrames(buffer: string) => { events: ChatEvent[]; rest: string }
 *
 * - `events`  — every *complete* frame in `buffer`, in order.
 * - `rest`    — the trailing partial frame, returned UNCHANGED so the caller can
 *               prepend it to the next chunk. Do not trim it.
 *
 * ## Hints from the traps below
 *
 * - `data:` may be absent. A frame with only `event:` and no data is legal.
 * - The buffer may end with `\r\n`. The server sends `\n`, but a proxy in the
 *   path is entitled to re-frame it, and a parser that splits only on `\n\n`
 *   leaves a stray `\r` glued to the start of every `data` value.
 * - A comment line (`:` …) is legal SSE and carries no event. `/health` and some
 *   proxies emit them as keep-alives. Skipping them is correct; treating one as
 *   an event with no name is not.
 * - `unknown` is a real `ChatEvent` kind. An event name this version does not
 *   know is not an error — it becomes `{ kind: "unknown", name, data }` so the
 *   backend can add one without breaking an older frontend. What matters is that
 *   it does not throw and does not silently vanish.
 */

import { describe, expect, test } from "bun:test";
import { parseSseFrames } from "./parse-sse";
import type { ChatEvent } from "./types";

/** The one-line shape most frames arrive in. */
function frame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/** Events of one kind, for terse assertions. */
function kinds(events: ChatEvent[]): string[] {
  return events.map((e) => e.kind);
}

// ── The happy path ──────────────────────────────────────────────────────────

describe("complete frames", () => {
  test("a single frame becomes one event", () => {
    const { events, rest } = parseSseFrames(frame("delta", { text: "hello" }));

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ kind: "delta", text: "hello" });
    expect(rest).toBe("");
  });

  test("several frames in one buffer are all returned, in order", () => {
    const buffer =
      frame("delta", { text: "one" }) +
      frame("citation", { source_path: "resume.md", label: "resume.md" }) +
      frame("done", { sources: ["resume.md"], text_length: 3 });

    const { events, rest } = parseSseFrames(buffer);

    expect(kinds(events)).toEqual(["delta", "citation", "done"]);
    expect(rest).toBe("");
  });

  test("an empty buffer yields nothing and is not an error", () => {
    // What a caller sees on the first poll of a stream that has not arrived yet.
    const { events, rest } = parseSseFrames("");

    expect(events).toHaveLength(0);
    expect(rest).toBe("");
  });
});

// ── The partial frame, which is the actual work ─────────────────────────────

describe("partial frames", () => {
  test("an incomplete frame is returned as rest, not parsed", () => {
    // The frame boundary has not arrived yet.
    const { events, rest } = parseSseFrames('event: delta\ndata: {"text":"hel');

    expect(events).toHaveLength(0);
    expect(rest).toBe('event: delta\ndata: {"text":"hel');
  });

  test("completing a split frame across two chunks yields one event", () => {
    // The realistic case: a chunk boundary in the middle of a JSON payload.
    const whole = frame("delta", { text: "the quick brown fox" });
    const cut = Math.floor(whole.length / 2);

    const first = parseSseFrames(whole.slice(0, cut));
    expect(first.events).toHaveLength(0);

    const second = parseSseFrames(first.rest + whole.slice(cut));
    expect(second.events).toHaveLength(1);
    expect(second.events[0]).toEqual({ kind: "delta", text: "the quick brown fox" });
  });

  test("a frame split on every possible boundary still parses exactly once", () => {
    // The property test. If any single split point loses or duplicates an event,
    // production will find it and a local run will not.
    const whole = frame("delta", { text: "split me" }) + frame("done", { sources: [], text_length: 8 });

    for (let cut = 1; cut < whole.length; cut++) {
      const first = parseSseFrames(whole.slice(0, cut));
      const second = parseSseFrames(first.rest + whole.slice(cut));

      expect(kinds([...first.events, ...second.events])).toEqual(["delta", "done"]);
    }
  });

  test("a frame split three ways is still one event", () => {
    const whole = frame("citation", { source_path: "a/b.md", label: "b.md" });

    const a = parseSseFrames(whole.slice(0, 5));
    const b = parseSseFrames(a.rest + whole.slice(5, 20));
    const c = parseSseFrames(b.rest + whole.slice(20));

    expect(kinds([...a.events, ...b.events, ...c.events])).toEqual(["citation"]);
  });

  test("rest is returned unchanged, not trimmed", () => {
    // Trimming would eat a leading space in `data: value`, which is required by
    // the SSE spec to be exactly one space.
    const { rest } = parseSseFrames("event: delta\ndata: {\"text\":");

    expect(rest).toBe("event: delta\ndata: {\"text\":");
  });
});

// ── Field shapes the spec allows and the server can produce ────────────────

describe("field handling", () => {
  test("a frame with only an event name and no data is still an event", () => {
    // Legal SSE. A parser that assumes `data:` always exists throws here.
    const { events } = parseSseFrames("event: ping\n\n");

    expect(events).toHaveLength(1);
  });

  test("multiple data lines in one frame are joined with a newline", () => {
    // The spec concatenates them. A single-line parser keeps only the first.
    const { events } = parseSseFrames('event: note\ndata: {"a":1,\ndata: "b":2}\n\n');

    expect(events).toHaveLength(1);
  });

  test("the space after the field colon is stripped, exactly one", () => {
    // `data: {"x":1}` — not `data:{"x":1}`. Missing the strip leaves invalid JSON.
    const { events } = parseSseFrames('event: delta\ndata: {"text":"hi"}\n\n');

    expect(events[0]).toEqual({ kind: "delta", text: "hi" });
  });

  test("a CRLF re-framed stream parses the same as an LF one", () => {
    // A proxy is entitled to re-frame. The server sends \n; the internet may
    // send \r\n, and a parser that splits only on "\n\n" leaves a stray \r glued
    // to the front of every data value.
    const lf = frame("delta", { text: "hi" });
    const crlf = lf.replace(/\n/g, "\r\n");

    expect(parseSseFrames(crlf).events).toEqual(parseSseFrames(lf).events);
  });

  test("a comment line is a keep-alive, not an event", () => {
    // SSE comment. Emitted by proxies between chunks.
    const { events } = parseSseFrames(": keep-alive\n\n" + frame("done", { sources: [], text_length: 0 }));

    expect(kinds(events)).toEqual(["done"]);
  });

  test("blank lines between frames do not produce empty events", () => {
    const { events } = parseSseFrames("\n\n" + frame("delta", { text: "a" }) + "\n\n\n");

    expect(events).toHaveLength(1);
  });
});

// ── Unknown and malformed events ────────────────────────────────────────────

describe("unknown and malformed", () => {
  test("an unrecognised event name becomes an unknown event, not a throw", () => {
    // The backend is allowed to add one. An older frontend must not break.
    const { events } = parseSseFrames(frame("typing", { at: 1 }));

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ kind: "unknown", name: "typing", data: { at: 1 } });
  });

  test("unknown events do not stop the frames after them", () => {
    const buffer = frame("typing", {}) + frame("done", { sources: [], text_length: 0 });

    const { events } = parseSseFrames(buffer);

    expect(kinds(events)).toEqual(["unknown", "done"]);
  });

  test("a frame whose data is not valid JSON does not throw", () => {
    // A truncated payload from a dropped connection. Throwing here loses every
    // answer already received, because the caller is mid-stream.
    const { events } = parseSseFrames("event: delta\ndata: {not json\n\n");

    // Either skip it or surface it as unknown. What matters is that it returns.
    expect(Array.isArray(events)).toBe(true);
  });

  test("a frame with no event name defaults to message, which is unknown here", () => {
    // `data:` alone is the anonymous form. The server never sends it.
    const { events } = parseSseFrames('data: {"text":"hi"}\n\n');

    expect(events).toHaveLength(1);
  });
});

// ── Every event the server can actually emit ───────────────────────────────

describe("the real event set", () => {
  test("parses one of each kind the backend emits", () => {
    const buffer =
      frame("delta", { text: "answer text" }) +
      frame("tool_call", { id: "1", name: "search_portfolio", arguments: '{"query":"x"}' }) +
      frame("tool_result", { id: "1", name: "search_portfolio", ok: true, result: {}, error: null }) +
      frame("citation", { source_path: "resume.md", label: "resume.md" }) +
      frame("draft", {
        id: 12,
        name: "Ada",
        sender_email: "ada@example.com",
        body: "Hello",
        approval_token: "TOKEN",
        expires_at: "2026-10-11T12:00:00Z",
      }) +
      frame("busy", { retry_after_seconds: 12, message: "Too many questions at once." }) +
      frame("error", { message: "Something went wrong. Try again." }) +
      frame("done", { sources: ["resume.md"], text_length: 12 });

    const { events } = parseSseFrames(buffer);

    expect(kinds(events)).toEqual([
      "delta",
      "tool_call",
      "tool_result",
      "citation",
      "draft",
      "busy",
      "error",
      "done",
    ]);
  });

  test("the draft event carries the approval token through unchanged", () => {
    // The token is the send capability. If the parser renames, drops or reshapes
    // it, the approve button silently stops working.
    const { events } = parseSseFrames(
      frame("draft", {
        id: 12,
        name: "Ada",
        sender_email: "ada@example.com",
        body: "Hello",
        approval_token: "abc123",
        expires_at: "2026-10-11T12:00:00Z",
      }),
    );

    const draft = events[0] as Extract<ChatEvent, { kind: "draft" }>;
    expect(draft.approvalToken).toBe("abc123");
    expect(draft.id).toBe(12);
  });

  test("done carries sourcesVerified, and only the literal true verifies", () => {
    // The badge's contract field. The backend's no-verifier value is `false`,
    // and anything the backend declines to send must decode the same way —
    // `undefined` reading as verified would light the badge for everyone.
    const decode = (payload: string) =>
      parseSseFrames(payload).events[0] as Extract<ChatEvent, { kind: "done" }>;

    expect(
      decode(
        frame("done", { sources: ["resume.md"], text_length: 9, sources_verified: true }),
      ).sourcesVerified,
    ).toBe(true);

    expect(
      decode(frame("done", { sources: [], text_length: 0, sources_verified: false }))
        .sourcesVerified,
    ).toBe(false);

    expect(decode(frame("done", { sources: [], text_length: 0 })).sourcesVerified).toBe(false);
  });

  test("camelCases the server's snake_case keys", () => {
    // The wire format is snake_case; TypeScript is camelCase. Doing that here
    // means the rest of the frontend never has to know which is which.
    const { events } = parseSseFrames(
      frame("citation", { source_path: "projects/a.md", label: "a.md" }),
    );

    expect(events[0]).toEqual({ kind: "citation", sourcePath: "projects/a.md", label: "a.md" });
  });

  test("the busy event carries the retry hint as a number", () => {
    const { events } = parseSseFrames(frame("busy", { retry_after_seconds: 12, message: "later" }));

    expect(events[0]).toEqual({ kind: "busy", retryAfterSeconds: 12, message: "later" });
  });
});