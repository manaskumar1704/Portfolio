import type { ChatMessage } from "@/lib/api/types";

/** One chat row: `>` for the user, glowing `✳` for the agent. */
export function Message({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className="flex animate-[msgin_260ms_var(--ease)_both] items-start gap-2.5 overflow-wrap-anywhere whitespace-pre-wrap">
      <span
        aria-hidden="true"
        className={`w-[1.1em] flex-none text-center ${
          isUser
            ? "text-dim"
            : "text-accent [text-shadow:0_0_8px_rgba(255,176,0,.4)]"
        }`}
      >
        {isUser ? ">" : "✳"}
      </span>
      <span className="min-w-0 flex-1 text-text">
        {message.thinking ? (
          <span className="dots text-dim">thinking</span>
        ) : (
          message.text
        )}
      </span>
    </div>
  );
}
