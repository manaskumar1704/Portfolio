"use client";

/**
 * The approve button — and, since the draft lifecycle, the discard beside it.
 * It renders the token; it never stores one.
 *
 * ## Why the token arrives as a function
 *
 * `readToken()` rather than `token={...}`.
 *
 * A prop is part of a component's public, serialisable surface: it shows up in
 * React DevTools, in any props-snapshotting debug hook, and in a test's rendered
 * output. A function prop is called, and the result never lands anywhere a tool
 * can see it.
 *
 * The parent (`useAgent`) holds the token in a `useRef`. This module cannot put
 * it in `useState`, `localStorage`, `sessionStorage`, a URL, or a `data-`
 * attribute, and does not. See ADR 0006 for why the model must never see it, and
 * this component for why the browser must hold it as briefly as possible.
 *
 * Reloading the page loses the token and therefore the ability to approve. That
 * is the intended failure mode: a capability that outlived the page would also
 * outlive the connection it was bound to.
 *
 * ## A settled card renders null, and why that is not abrupt
 *
 * The parent decides what a settled draft leaves behind: the chat leaves a
 * one-line "Sent to Manas." confirmation, and the form returns to its fields
</think><tool_call>edit<arg_key>newString</arg_key><arg_value> * The parent decides what a settled draft leaves behind: the chat leaves a
 * one-line "Sent to Manas." confirmation, and the form returns to its fields
 * with a "Sent — thank you." line. A
 * terminal view rendered here would never paint — both parents unmount in the
 * same commit as the callback — so the states below are exactly three: busy
 * (while the request runs), errored (the visitor reads why), and settled (null).
 */

import { useState } from "react";

import { sendApproval } from "@/lib/api/draft-approve";
import { cancelDraft } from "@/lib/api/drafts";
import type { Draft } from "@/lib/api/types";

/** Shown when the token is gone but the card is still here. */
const LOST_TOKEN =
  "This approval link was lost when the page reloaded. Write the message again to get a new one.";

export function DraftApproval({
  draft,
  /** Called once, then the token is gone. Returns the token or null. */
  readToken,
  onSent,
  onDiscard,
}: {
  draft: Draft;
  readToken: () => string | null;
  onSent: () => void;
  /** Entered when a withdrawal is recorded; the parent decides what remains. */
  onDiscard?: () => void;
}) {
  const [working, setWorking] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const [settled, setSettled] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const approve = async () => {
    if (working || discarding || settled) return;

    const token = readToken();
    if (!token) {
      setError(LOST_TOKEN);
      return;
    }

    setWorking(true);
    setError(null);

    const result = await sendApproval({ messageId: draft.id, token });
    // The token has been spent either way. The reader returns null from here on,
    // so it cannot be replayed from this button by a second click.
    setWorking(false);

    if (result.ok) {
      setSettled(true);
      onSent();
    } else {
      setError(result.message);
    }
  };

  const discard = async () => {
    if (working || discarding || settled) return;

    const token = readToken();
    if (!token) {
      setError(LOST_TOKEN);
      return;
    }

    setDiscarding(true);
    setError(null);

    const result = await cancelDraft({ messageId: draft.id, token });
    setDiscarding(false);

    if (result.ok) {
      setSettled(true);
      onDiscard?.();
    } else {
      setError(result.message);
    }
  };

  if (settled) return null;

  return (
    <div className="draft" role="group" aria-label="Message approval">
      <div className="draft-head">
        <span className="draft-label">Ready to send</span>
        <span className="draft-to">to {draft.name}</span>
      </div>

      {/* The visitor approves what they will actually send, so the body is shown
          in full rather than as the truncated preview from the stream event. */}
      <p className="draft-body">{draft.body}</p>

      <button type="button" className="draft-approve" onClick={approve} disabled={working}>
        {working ? "Sending…" : "Send this message"}
      </button>

      {/* Withdrawing is as first-class as approving: the row exists because the
          draft is the visitor's to retract before it is the owner's to read. */}
      <button
        type="button"
        className="draft-discard"
        onClick={discard}
        disabled={discarding}
      >
        {discarding ? "Withdrawing…" : "Discard"}
      </button>

      {error && (
        <p className="draft-failed" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
