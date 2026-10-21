import type { ChatMessage } from "@/lib/api/types";
import { AgentMarkdown } from "./markdown";
import { Citations } from "./citations";

/**
 * One chat row: `>` for the user, glowing `✳` for the agent.
 *
 * The agent's text goes through `AgentMarkdown` rather than being rendered as
 * plain text. A model writes lists and tables, and `whitespace-pre-wrap` on a
 * markdown bullet produces a wall of misaligned characters. It also means the
 * rendering path has to be safe, which is the reason `AgentMarkdown` exists and
 * the reason it refuses raw HTML — see ADR 0007.
 *
 * The user's own text is rendered as text. It is not model output, but treating
 * it identically is the cheaper rule and the one with no exceptions to
 * remember.
 */
export function Message({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className="flex animate-[msgin_260ms_var(--ease)_both] items-start gap-2.5 overflow-wrap-anywhere">
      <span
        aria-hidden="true"
        className={`w-[1.1em] flex-none pt-[0.1em] text-center ${
          isUser
            ? "text-dim"
            : "text-accent [text-shadow:0_0_8px_rgba(255,176,0,.4)]"
        }`}
      >
        {isUser ? ">" : "✳"}
      </span>

      <div className="min-w-0 flex-1 text-text">
        {message.thinking ? (
          <span className="dots text-dim">thinking</span>
        ) : (
          <AgentMarkdown text={message.text} />
        )}

        {message.citations && message.citations.length > 0 && (
          <Citations citations={message.citations} />
        )}

        {/*
          The verification badge. This release never renders it: no verifier is
          wired (services/verify.py), so `sourcesVerified` is always false, and
          a badge nobody earned is a lie. The branch is the contract — the day a
          verifier flips the field, this is where the visitor sees it.
        */}
        {message.sourcesVerified === true && (
          <div className="my-2 flex items-center gap-1.5 text-[0.86em] text-ok">
            <span aria-hidden="true" className="w-[1.1em] text-center">
              ✔
            </span>
            sources verified
          </div>
        )}
      </div>
    </div>
  );
}