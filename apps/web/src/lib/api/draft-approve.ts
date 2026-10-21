/**
 * The approval: POST the token to the send route, report the outcome in words.
 *
 * ## Why the browser calls Render directly
 *
 * Same reason as `sse.ts`. The route matches the draft to the IP that created
 * it, and a route handler on Vercel would replace the visitor's address with
 * Vercel's. Direct calls are why CORS is a strict allowlist on the API.
 *
 * ## The six outcomes
 *
 * 200 is the only success. Five statuses are refusals the visitor can act on,
 * and "no response at all" is the sixth. Two of them look the same on purpose:
 * the 403 is wrong token, wrong network and no such message at once, because a
 * more specific refusal would confirm which message ids exist. The message
 * this module produces never claims the draft was found.
 *
 * ## The token is not ours
 *
 * It arrives through a component's React ref, goes into one request body, and
 * is dropped. Nothing here caches it, retries with it, or writes it anywhere
 * persistent — the whole design assumes it dies with the page. It also never
 * goes in a URL: that lands it in access logs, browser history and Referer.
 */

import { apiUrl } from "./config";
import type { SendFailure, SendResult } from "./types";

/** What the composer's approve flow needs. */
export type SendArgs = {
  messageId: number;
  token: string;
  signal?: AbortSignal;
};

/** Status → failure word, for the five statuses this route actually returns. */
const REASONS: Record<number, SendFailure> = {
  403: "refused",
  409: "already",
  410: "expired",
  429: "cap",
  503: "unavailable",
};

/**
 * Local wording, used only when the server does not explain itself.
 *
 * The server's own `reason` is preferred — it is written for exactly this
 * moment — but the 403 body arrives without context-protection fields in every
 * case, and the fallback below is what the visitor reads first: the likeliest
 * cause, stated, without confirming anything about a draft.
 */
export const NETWORK_MESSAGE =
  "The site could not be reached. Check the connection and try again.";

const FALLBACKS: Record<SendFailure, string> = {
  refused:
    "That could not be approved. This usually means the connection changed — " +
    "if you switched from wifi to mobile data since writing the message, please " +
    "start a new message from this device.",
  already: "That message has already been handled.",
  expired: "That message has expired. Please write it again.",
  cap: "The owner is receiving a high volume of messages and has reached today's limit. Please try again tomorrow.",
  unavailable: "This site cannot send messages right now. Please try again later.",
  network: NETWORK_MESSAGE,
};

export async function sendApproval(args: SendArgs): Promise<SendResult> {
  let response: Response;
  try {
    response = await fetch(apiUrl(`/messages/${args.messageId}/send`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: args.token }),
      cache: "no-store",
      signal: args.signal,
    });
  } catch {
    // No response at all: Render asleep, mid-deploy, offline, or the page
    // navigated away and aborted the fetch. Every one of those resolves here
    // rather than rejecting — the component may have unmounted already, and a
    // callback racing an unmount must not throw into it.
    return { ok: false, reason: "network", message: FALLBACKS.network };
  }

  if (response.status === 200) return { ok: true };

  const failure = REASONS[response.status] ?? "unavailable";
  const serverExplanation = await serverReason(response);

  return {
    ok: false,
    reason: failure,
    message: serverExplanation ?? FALLBACKS[failure],
  };
}

/**
 * The server's own explanation, when it gives one.
 *
 * The send route answers refusals with a `reason` written for exactly this
 * moment, so it is used verbatim. The edit and cancel routes raise standard
 * HTTP exceptions — same codes, same words, but under `detail` — so both keys
 * are read, in that order. Only a legible string becomes the message; anything
 * else (a non-JSON body, a list-shaped validation `detail`) falls back to local
 * wording.
 */
export async function serverReason(response: Response): Promise<string | null> {
  try {
    const payload = (await response.json()) as { reason?: unknown; detail?: unknown };
    if (typeof payload.reason === "string" && payload.reason.length > 0) {
      return payload.reason;
    }
    if (typeof payload.detail === "string" && payload.detail.length > 0) {
      return payload.detail;
    }
  } catch {
    // Not JSON, or not a body. The fallback is better anyway.
  }
  return null;
}
