/**
 * The contact form's client: create a draft from the form, cancel one.
 *
 * ## One row, two issuers
 *
 * `createDraft` is the form's issuer (`POST /messages/drafts`); the other is
 * the `draft_message` tool reached through the chat stream. Both write the
 * same `pending` row, bind it to the visitor's connection, and hand back a
 * token the server keeps only the SHA-256 of. Create issues a token and needs
 * none — acting on a draft is what is protected.
 *
 * ## The token is not ours, again
 *
 * Same rule as `draft-approve.ts` (ADR 0006): the token is handed back once
 * and this module caches nothing. The caller holds it in a ref for as long as
 * the approval control lives, and drops it the moment it is spent.
 */

import { apiUrl } from "@/lib/api/config";
import { NETWORK_MESSAGE, serverReason } from "@/lib/api/draft-approve";
import type { Draft } from "@/lib/api/types";

/** What the form collects. Everything after the first two is optional context. */
export type DraftFormFields = {
  name: string;
  senderEmail: string;
  subject: string;
  company: string;
  role: string;
  body: string;
};

export type CreateDraftResult =
  | { ok: true; draft: Draft; token: string }
  | { ok: false; message: string };

/** When the server explains nothing, this is all the explanation there is. */
const FALLBACK = "That did not go through. Please try again.";

export async function createDraft(fields: DraftFormFields): Promise<CreateDraftResult> {
  try {
    const response = await fetch(apiUrl("/messages/drafts"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // decision 6: the wire spells the visitor's address sender_email; the
      // tool argument and the database column stay email on the API's side.
      body: JSON.stringify({
        name: fields.name,
        sender_email: fields.senderEmail,
        body: fields.body,
        company: fields.company || undefined,
        role: fields.role || undefined,
        subject: fields.subject || undefined,
      }),
      cache: "no-store",
    });

    if (response.status === 201) {
      const payload = (await response.json()) as {
        id: number;
        name: string;
        sender_email: string;
        body: string;
        expires_at: string;
        token: string;
      };
      return {
        ok: true,
        draft: {
          id: payload.id,
          name: payload.name,
          senderEmail: payload.sender_email,
          body: payload.body,
          expiresAt: payload.expires_at,
        },
        token: payload.token,
      };
    }

    // 422 is a fixable content problem — the service's own words say which
    // field and why. 429 shares the approval budget and explains the wait.
    // Anything else gets the generic line rather than a guess.
    return { ok: false, message: (await serverReason(response)) ?? FALLBACK };
  } catch {
    return { ok: false, message: NETWORK_MESSAGE };
  }
}

export async function cancelDraft(args: {
  messageId: number;
  token: string;
}): Promise<{ ok: true } | { ok: false; message: string }> {
  try {
    const response = await fetch(apiUrl(`/messages/${args.messageId}/cancel`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: args.token }),
      cache: "no-store",
    });

    if (response.ok) return { ok: true };

    // Refusals share the send route's codes and, since the shared helper, its
    // exact words — 403 for anything unrecognisable, 410 when time ran out,
    // 429 when the shared budget is spent.
    return { ok: false, message: (await serverReason(response)) ?? FALLBACK };
  } catch {
    return { ok: false, message: NETWORK_MESSAGE };
  }
}
