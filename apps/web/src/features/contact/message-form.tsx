"use client";

/**
 * The contact form: the draft issuer that needs no model.
 *
 * The chat path asks the model to call `draft_message` and shows the resulting
 * card; this path skips the model entirely — the visitor types into the panel
 * and `POST /messages/drafts` writes the same `pending` row. From there the
 * approval step is identical, and that is the point: a form the model never
 * touched still ends at the same explicit approve, because the boundary that
 * matters was never between issuers, it is between drafting and sending.
 *
 * The token the create returns lives in a ref for the same reason as in the
 * chat path (ADR 0006): never in React state, never in storage, dropped the
 * moment it is spent.
 */

import { useRef, useState } from "react";

import { ContactRow } from "@/components/ui/contact-row";
import { createDraft, type DraftFormFields } from "@/lib/api/drafts";
import type { Draft } from "@/lib/api/types";

import { DraftApproval } from "./draft-approval";

/* The backend's caps, restated as browser maxLengths so a too-long field stops
   in the input itself rather than costing a 422 round-trip to find out. */
const MAX_NAME = 200;
const MAX_EMAIL = 320;
const MAX_META = 200;
const MAX_BODY = 4000;

type Stage = "edit" | "recorded" | "sent";

const FIELD_STYLE =
  "w-full min-w-0 border border-border bg-panel-2 px-2 py-1 text-[0.95em] text-text " +
  "placeholder:text-faint focus:outline focus:outline-1 focus:outline-accent";

export function MessageForm() {
  const [stage, setStage] = useState<Stage>("edit");
  const [fields, setFields] = useState<DraftFormFields>({
    name: "",
    senderEmail: "",
    subject: "",
    company: "",
    role: "",
    body: "",
  });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tokenRef = useRef<string | null>(null);

  const set =
    (key: keyof DraftFormFields) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setFields((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (working || stage !== "edit") return;

    setWorking(true);
    setError(null);

    const result = await createDraft(fields);
    setWorking(false);

    if (!result.ok) {
      setError(result.message);
      return;
    }

    tokenRef.current = result.token;
    setDraft(result.draft);
    setStage("recorded");
  };

  /** Back to the fields. Whatever the token was, it is spent or obsolete. */
  const forget = () => {
    tokenRef.current = null;
    setDraft(null);
    setStage("edit");
  };

  if (stage === "recorded" && draft) {
    return (
      <div className="mt-4 border-t border-border pt-3">
        <p className="m-0 text-dim">
          Recorded — review below. Nothing is sent without an explicit approval.
        </p>
        <div className="mt-3">
          <DraftApproval
            draft={draft}
            readToken={() => tokenRef.current}
            onSent={() => setStage("sent")}
            onDiscard={forget}
          />
        </div>
      </div>
    );
  }

  if (stage === "sent") {
    return (
      <div className="mt-4 border-t border-border pt-3" role="status">
        <p className="m-0 text-dim">
          <span className="draft-tick" aria-hidden="true">
            ✓
          </span>
          Sent — thank you.
        </p>
        <button
          type="button"
          onClick={forget}
          className="mt-2 cursor-pointer text-accent underline underline-offset-2"
        >
          write another
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="mt-4 border-t border-border pt-3">
      <div className="grid gap-1.5">
        <ContactRow k="name">
          <input
            className={FIELD_STYLE}
            value={fields.name}
            onChange={set("name")}
            required
            maxLength={MAX_NAME}
            autoComplete="name"
            aria-label="Your name"
            placeholder="who you are"
          />
        </ContactRow>
        <ContactRow k="email">
          <input
            className={FIELD_STYLE}
            type="email"
            value={fields.senderEmail}
            onChange={set("senderEmail")}
            required
            maxLength={MAX_EMAIL}
            autoComplete="email"
            aria-label="Your email address"
            placeholder="you@example.com"
          />
        </ContactRow>
        <ContactRow k="about">
          <input
            className={FIELD_STYLE}
            value={fields.subject}
            onChange={set("subject")}
            maxLength={MAX_META}
            aria-label="What this is about (optional)"
            placeholder="what this is about (optional)"
          />
        </ContactRow>
        <ContactRow k="company">
          <input
            className={FIELD_STYLE}
            value={fields.company}
            onChange={set("company")}
            maxLength={MAX_META}
            autoComplete="organization"
            aria-label="Your company (optional)"
            placeholder="where you work (optional)"
          />
        </ContactRow>
        <ContactRow k="role">
          <input
            className={FIELD_STYLE}
            value={fields.role}
            onChange={set("role")}
            maxLength={MAX_META}
            autoComplete="organization-title"
            aria-label="Your role (optional)"
            placeholder="what you do there (optional)"
          />
        </ContactRow>
      </div>

      <textarea
        className={`${FIELD_STYLE} mt-1.5 min-h-[7rem]`}
        value={fields.body}
        onChange={set("body")}
        required
        maxLength={MAX_BODY}
        aria-label="Your message"
        placeholder="the message — plain text, no formatting needed"
      />

      {error && (
        <p className="mt-2 text-err" role="alert">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={working}
        className="mt-2 cursor-pointer rounded-[var(--radius)] border-0 bg-accent px-3 py-1 text-accent-foreground hover:brightness-110 disabled:cursor-default disabled:opacity-55"
      >
        {working ? "Recording…" : "Record the message"}
      </button>

      <p className="mt-2 text-[0.85em] text-faint">
        Recording makes a draft — it waits for your approval and nothing is sent
        until then.
      </p>
    </form>
  );
}
