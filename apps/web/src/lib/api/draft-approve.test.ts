/**
 * YOU IMPLEMENT THIS FILE. `draft-approve.ts` does not exist yet.
 *
 * The tests below are the specification. They are red until you write it.
 *
 * ## What it has to do
 *
 * POST an approval to the send route and turn the six possible responses into
 * something the UI can render without knowing HTTP.
 *
 * ## The route
 *
 * `POST /messages/{id}/send` with a JSON body of `{ "token": "..." }`.
 *
 * Three factors must line up on the server: the token, the visitor's IP, and an
 * unexpired pending row. Two of the six outcomes below are the interesting ones
 * because they mean the *same* thing to the visitor but arrive as different
 * codes, and one because the server deliberately refuses to say which of three
 * things went wrong.
 *
 * ## Signature the tests import
 *
 *     sendApproval(args: SendArgs): Promise<SendResult>
 *
 *     type SendArgs = {
 *       messageId: number
 *       token: string
 *       signal?: AbortSignal
 *     }
 *
 *     type SendResult =
 *       | { ok: true }
 *       | { ok: false; reason: SendFailure; message: string }
 *
 * `SendResult` and `SendFailure` already exist in `./types` — import them, do not
 * redefine them.
 *
 * ## Rules the tests pin
 *
 * ### The 403 is three different failures and the server will not say which
 *
 * Wrong token, wrong network, and no such message all return 403 with
 * byte-identical bodies. That is deliberate: distinguishing them would turn the
 * route into an oracle for guessing which message ids exist. Your job is to
 * present one honest message that covers all three, and not to imply the draft
 * was found.
 *
 * ### The token must never be logged
 *
 * It is a send capability, not an identifier. The test suite cannot enforce
 * that at runtime, so the one below checks the message you produce does not
 * contain it.
 *
 * ### Nothing is stored
 *
 * The token lives in a React ref for the lifetime of the page. Not
 * `localStorage`, not `sessionStorage`, not a URL, not `data-*`, not rendered
 * text. This module must not write it anywhere either — no caching layer, no
 * retry queue in storage. If you find yourself wanting to persist it across a
 * reload, that is the security boundary telling you no.
 */

import { describe, expect, test } from "bun:test";
import { sendApproval } from "./draft-approve";
import type { SendFailure } from "./types";

const TOKEN = "an-unguessable-approval-token";
const MESSAGE_ID = 42;

/** A fetch that answers with one status and body. */
function stubFetch(status: number, body: unknown = {}) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fake = async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init: init ?? {} });
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  };
  return { fake: fake as unknown as typeof fetch, calls };
}

/** Install a stub for one call. Returns the recorded requests. */
function withFetch(status: number, body: unknown = {}, onCall?: () => void) {
  const original = globalThis.fetch;
  const { fake, calls } = stubFetch(status, body);
  globalThis.fetch = (input: string | URL | Request, init?: RequestInit) => {
    onCall?.();
    return fake(input, init);
  };
  return {
    calls,
    restore: () => {
      globalThis.fetch = original;
    },
  };
}

// ── Success ─────────────────────────────────────────────────────────────────

describe("a successful approval", () => {
  test("returns ok for a 200", async () => {
    const stub = withFetch(200, { sent: true, message_id: MESSAGE_ID });

    try {
      expect(await sendApproval({ messageId: MESSAGE_ID, token: TOKEN })).toEqual({ ok: true });
    } finally {
      stub.restore();
    }
  });

  test("posts to the send route with the message id in the path", async () => {
    const stub = withFetch(200, { sent: true, message_id: MESSAGE_ID });

    try {
      await sendApproval({ messageId: MESSAGE_ID, token: TOKEN });
      expect(stub.calls[0].url).toContain(`/messages/${MESSAGE_ID}/send`);
    } finally {
      stub.restore();
    }
  });

  test("sends the token in a JSON body, not as a header or a query param", async () => {
    // A token in a URL lands in access logs, browser history and Referer headers.
    const stub = withFetch(200, { sent: true, message_id: MESSAGE_ID });

    try {
      await sendApproval({ messageId: MESSAGE_ID, token: TOKEN });
      const call = stub.calls[0];

      expect(call.init.method).toBe("POST");
      expect(JSON.parse(String(call.init.body))).toEqual({ token: TOKEN });
      expect(call.url).not.toContain(TOKEN);
    } finally {
      stub.restore();
    }
  });
});

// ── The refusals, each of which the visitor can act on ──────────────────────

describe("refusals", () => {
  const cases: { status: number; reason: SendFailure; note: string }[] = [
    { status: 403, reason: "refused", note: "wrong token, wrong IP, or no such message" },
    { status: 409, reason: "already", note: "already sent, or a concurrent request won" },
    { status: 410, reason: "expired", note: "the draft aged out" },
    { status: 429, reason: "cap", note: "the owner's daily send cap" },
    { status: 503, reason: "unavailable", note: "email is not configured on the server" },
  ];

  for (const { status, reason, note } of cases) {
    test(`a ${status} becomes "${reason}" (${note})`, async () => {
      const stub = withFetch(status, { sent: false, message_id: MESSAGE_ID, reason: "..." });

      try {
        const result = await sendApproval({ messageId: MESSAGE_ID, token: TOKEN });

        expect(result.ok).toBe(false);
        if (!result.ok) expect(result.reason).toBe(reason);
      } finally {
        stub.restore();
      }
    });
  }

  test("a network failure becomes network, not a thrown error", async () => {
    // Render is asleep, Render just deployed, or the visitor is on a train. The
    // UI needs a message it can show, not an exception with a stack trace.
    const original = globalThis.fetch;
    globalThis.fetch = (() => Promise.reject(new TypeError("Failed to fetch"))) as typeof fetch;

    try {
      const result = await sendApproval({ messageId: MESSAGE_ID, token: TOKEN });

      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.reason).toBe("network");
    } finally {
      globalThis.fetch = original;
    }
  });

  test("an unexpected status is still a result, not a throw", async () => {
    const stub = withFetch(500, { detail: "Internal Server Error" });

    try {
      const result = await sendApproval({ messageId: MESSAGE_ID, token: TOKEN });

      expect(result.ok).toBe(false);
    } finally {
      stub.restore();
    }
  });

  test("every failure carries a message a visitor can read", async () => {
    for (const status of [403, 409, 410, 429, 503]) {
      const stub = withFetch(status, { sent: false, reason: "server text" });

      try {
        const result = await sendApproval({ messageId: MESSAGE_ID, token: TOKEN });

        expect(result.ok).toBe(false);
        if (!result.ok) {
          expect(typeof result.message).toBe("string");
          expect(result.message.length).toBeGreaterThan(10);
        }
      } finally {
        stub.restore();
      }
    }
  });
});

// ── The properties that matter more than the mapping ───────────────────────

describe("the 403", () => {
  test("does not imply the draft was found", async () => {
    // "We found your message but the token was wrong" confirms the id exists to
    // anyone guessing ids. "That could not be approved" confirms nothing.
    const stub = withFetch(403, { sent: false, message_id: MESSAGE_ID });

    try {
      const result = await sendApproval({ messageId: MESSAGE_ID, token: TOKEN });

      if (!result.ok) {
        expect(result.message.toLowerCase()).not.toContain("found your message");
        expect(result.message.toLowerCase()).not.toContain("expired");
        expect(result.message.toLowerCase()).not.toContain("already sent");
      }
    } finally {
      stub.restore();
    }
  });

  test("explains the likely cause without confirming anything", async () => {
    // The most common cause by far is a visitor switching from wifi to mobile
    // between writing and approving. Saying so saves a support email.
    const stub = withFetch(403, { sent: false });

    try {
      const result = await sendApproval({ messageId: MESSAGE_ID, token: TOKEN });

      if (!result.ok) {
        expect(result.message.toLowerCase()).toContain("connection");
      }
    } finally {
      stub.restore();
    }
  });
});

describe("the token", () => {
  test("never appears in the message shown to the visitor", async () => {
    const stub = withFetch(403, { sent: false });

    try {
      const result = await sendApproval({ messageId: MESSAGE_ID, token: TOKEN });

      if (!result.ok) expect(result.message).not.toContain(TOKEN);
    } finally {
      stub.restore();
    }
  });

  test("is not written to storage", async () => {
    // A token in localStorage outlives the page, and the whole design assumes
    // it dies with it.
    const stub = withFetch(200, { sent: true, message_id: MESSAGE_ID });

    const setItem = () => {
      throw new Error("storage was written to during an approval");
    };
    const originalLocal = globalThis.localStorage;
    const originalSession = globalThis.sessionStorage;

    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      value: { setItem, getItem: () => null, removeItem: () => {} },
    });
    Object.defineProperty(globalThis, "sessionStorage", {
      configurable: true,
      value: { setItem, getItem: () => null, removeItem: () => {} },
    });

    try {
      await sendApproval({ messageId: MESSAGE_ID, token: TOKEN });
    } finally {
      stub.restore();
      Object.defineProperty(globalThis, "localStorage", {
        configurable: true,
        value: originalLocal,
      });
      Object.defineProperty(globalThis, "sessionStorage", {
        configurable: true,
        value: originalSession,
      });
    }
  });
});

describe("aborting", () => {
  test("an aborted request resolves rather than throwing", async () => {
    // Navigating away mid-approval must not produce an unhandled rejection in
    // a component that has already unmounted.
    const controller = new AbortController();
    const original = globalThis.fetch;

    globalThis.fetch = ((_url: string, init?: RequestInit) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      })) as unknown as typeof fetch;

    try {
      const pending = sendApproval({
        messageId: MESSAGE_ID,
        token: TOKEN,
        signal: controller.signal,
      });
      controller.abort();

      const result = await pending;
      expect(result.ok).toBe(false);
    } catch {
      // Throwing is acceptable for an abort, but returning is better. The test
      // allows either rather than mandating a shape the UI then has to handle.
    } finally {
      globalThis.fetch = original;
    }
  });
});