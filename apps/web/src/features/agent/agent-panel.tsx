"use client";

import { usePathname } from "next/navigation";
import { Composer } from "@/components/ui/composer";
import { PanelCap } from "@/components/ui/panel-cap";
import { AgentBackground } from "@/features/background/agent-background";
import { DraftApproval } from "@/features/contact/draft-approval";
import { PrivacyNote } from "@/features/contact/privacy-note";
import { Landing } from "./landing";
import { Message } from "./message";
import { useAgent } from "./use-agent";

/**
 * The agent console: background, panel, log, landing layer, composer.
 *
 * Full height on home, where it is the hero. Shorter elsewhere, so the folder
 * or file the visitor just `cd`-ed into is visible without scrolling.
 *
 * The composer says `waking…` while the free tier's cold start is in progress,
 * which is the only place `status` is surfaced. Everything else is in the log.
 */
export function AgentPanel() {
  const { messages, value, busy, dismissed, status, draft, readToken, clearDraft, onValueChange, send, dismiss } =
    useAgent();
  const isHome = usePathname() === "/";

  return (
    <section
      id="home"
      className={`relative flex scroll-mt-16 overflow-hidden border-b border-border ${
        isHome
          ? "min-h-[calc(100dvh-90px)] max-[640px]:min-h-[calc(100dvh-84px)]"
          : "min-h-[min(420px,52dvh)]"
      }`}
    >
      <AgentBackground />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 [background:radial-gradient(70%_60%_at_26%_40%,rgba(11,13,16,.42),rgba(11,13,16,.86)_72%),linear-gradient(180deg,rgba(11,13,16,.6),rgba(11,13,16,.82)_60%,var(--background))]"
      />

      <div className="relative z-[2] mx-auto flex w-[min(900px,100%)] flex-col px-[clamp(14px,4vw,40px)] py-[clamp(18px,3vw,34px)]">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[var(--radius)] border border-border bg-[linear-gradient(180deg,rgba(14,18,22,.82),rgba(11,15,19,.9))] backdrop-blur-[6px]">
          <div className="px-3 pt-2">
            <PanelCap label="ask manas" />
          </div>

          <div className="relative flex min-h-0 flex-1">
            <div
              role="log"
              aria-live="polite"
              aria-label="Conversation with Manas's agent"
              className={`min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto px-4 p-3.5 overscroll-contain ${
                dismissed || !isHome
                  ? "flex animate-[logIn_520ms_var(--ease)_both]"
                  : "flex opacity-0"
              }`}
            >
              {messages.map((m) => (
                <Message key={m.id} message={m} />
              ))}

              {draft && (
                <DraftApproval draft={draft} readToken={readToken} onSent={clearDraft} />
              )}
            </div>
            {isHome ? <Landing dismissed={dismissed} /> : null}
          </div>

          <div onFocusCapture={dismiss} onPointerDownCapture={dismiss}>
            <Composer
              value={value}
              busy={busy}
              placeholder={status === "waking" ? "waking the agent…" : undefined}
              onValueChange={onValueChange}
              onSubmit={() => void send()}
            />
            <PrivacyNote />
          </div>

          <div className="px-3 pt-2">
            <PanelCap variant="bottom" />
          </div>
        </div>
      </div>
    </section>
  );
}
