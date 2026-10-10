"use client";

/**
 * The approve button. It renders the token; it never stores one.
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
 */

import { useState } from "react";

import { sendApproval } from "@/lib/api/draft-approve";
import type { Draft } from "@/lib/api/types";

export function DraftApproval({
  draft,
  /** Called once, then the token is gone. Returns the token or null. */
  readToken,
  onSent,
}: {
  draft: Draft;
  readToken: () => string | null;
  onSent: () => void;
}) {
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const approve = async () => {
    if (working || done) return;

    const token = readToken();
    if (!token) {
      setError(
        "This approval link was lost when the page reloaded. Write the message again to get a new one.",
      );
      return;
    }

    setWorking(true);
    setError(null);

    const result = await sendApproval({ messageId: draft.id, token });
    // The token has been spent either way. The reader returns null from here on,
    // so it cannot be replayed from this button by a second click.
    setWorking(false);

    if (result.ok) {
      setDone(true);
      onSent();
    } else {
      setError(result.message);
    }
  };

  if (done) {
    return (
      <div className="draft draft-sent" role="status">
        <span className="draft-tick" aria-hidden="true">
          ✓
        </span>
        Sent to Manas.
      </div>
    );
  }

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

      {error && (
        <p className="draft-failed" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}