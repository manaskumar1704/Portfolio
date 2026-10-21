"use client";

import { useEffect, useState } from "react";

import { ContactRow } from "@/components/ui/contact-row";
import { PanelCap } from "@/components/ui/panel-cap";
import { Reveal } from "@/components/ui/reveal";
import { SectionHead } from "@/components/ui/section-head";
import { getContact } from "@/lib/api/contact";
import { useAsync } from "@/lib/api/use-async";

import { MessageForm } from "./message-form";

/** Contact section: the contact.sh panel with loading / error states. */
export function ContactSection() {
  const { status, data, retry } = useAsync(getContact);
  const [formOpen, setFormOpen] = useState(false);

  // `/contact` in the agent console opens this form. The console hook and this
  // section are different component trees, so the hand-off is one custom event —
  // no shared context, no store, and the name in one place per side.
  useEffect(() => {
    const open = () => setFormOpen(true);
    window.addEventListener("contact:open", open);
    return () => window.removeEventListener("contact:open", open);
  }, []);

  return (
    <section id="contact" className="scroll-mt-16 py-[clamp(44px,7vw,84px)]">
      <Reveal>
        <SectionHead index="02" title="contact" />
      </Reveal>

      <Reveal>
        <div className="rounded-[var(--radius)] border border-border bg-panel">
          <div className="px-3 pt-2">
            <PanelCap label="contact.sh" />
          </div>

          <div className="px-4 pb-4 pt-3.5 text-[0.95em]">
            <div className="flex items-start gap-2.5 whitespace-pre-wrap">
              <span aria-hidden="true" className="w-[1.1em] flex-none text-center text-dim">
                &gt;
              </span>
              <span className="text-text">
                ./contact --email --github --linkedin
              </span>
            </div>

            <div className="mt-3 grid gap-1.5">
              {status === "loading" ? (
                <>
                  <div className="h-5 w-48 animate-pulse bg-panel-2" />
                  <div className="h-5 w-56 animate-pulse bg-panel-2" />
                  <div className="h-5 w-60 animate-pulse bg-panel-2" />
                </>
              ) : status === "error" ? (
                <p className="m-0 text-err" role="alert">
                  Failed to load contact details.{" "}
                  <button
                    type="button"
                    onClick={retry}
                    className="cursor-pointer text-accent underline"
                  >
                    retry
                  </button>
                </p>
              ) : status === "empty" || !data ? (
                <p className="m-0 text-dim">No contact details configured.</p>
              ) : (
                <>
                  <ContactRow k="email">
                    <a href={`mailto:${data.email}`}>{data.email}</a>
                  </ContactRow>
                  <ContactRow k="github">
                    <a href={data.github} target="_blank" rel="noopener noreferrer">
                      {data.github.replace("https://", "")}
                    </a>
                  </ContactRow>
                  <ContactRow k="linkedin">
                    <a
                      href={data.linkedin}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {data.linkedin.replace("https://", "")}
                    </a>
                  </ContactRow>
                </>
              )}
            </div>

            {data ? (
              <p className="mt-3.5 text-[0.9em] text-faint">{data.note}</p>
            ) : null}

            {/* The second draft issuer. The chat can ask the model to draft;
                this needs no model — and both end at the same approval. */}
            {formOpen ? (
              <MessageForm />
            ) : (
              <div className="mt-4 border-t border-border pt-2.5">
                <button
                  type="button"
                  onClick={() => setFormOpen(true)}
                  className="cursor-pointer text-accent hover:underline"
                >
                  ./message --new
                </button>
                <span className="ml-2 text-faint">write to the owner&apos;s inbox</span>
              </div>
            )}
          </div>

          <div className="px-3 pt-2">
            <PanelCap variant="bottom" />
          </div>
        </div>
      </Reveal>
    </section>
  );
}
