"use client";

/**
 * The up arrow, inlined. One glyph for the whole site: `lucide-react` ships a
 * tree of icons for what a single <svg> does natively, so the dependency went
 * and the 1-em stroke set it drew stays, copied verbatim from its ArrowUp.
 */

type ComposerProps = {
  value: string;
  busy: boolean;
  onValueChange: (value: string) => void;
  onSubmit: () => void;
  /**
   * Replaces the default prompt. Used for `waking…` while a sleeping free-tier
   * instance is being woken — the alternative is an input that looks live and
   * silently swallows the first question.
   */
  placeholder?: string;
};

/** Prompt bar: `> input [↑]`. Turns amber while the agent is busy. */
export function Composer({
  value,
  busy,
  onValueChange,
  onSubmit,
  placeholder = "Ask anything about Manas…",
}: ComposerProps) {
  const disabled = value.trim().length === 0 || busy;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!disabled) onSubmit();
      }}
      className="mx-4 mb-4 mt-3 flex items-center gap-2.5 rounded-[var(--radius)] border border-border-hi bg-inset px-3.5 py-2 transition-colors duration-[var(--dur)] ease-[var(--ease)] focus-within:border-accent"
    >
      <span aria-hidden="true" className="flex-none text-accent">
        &gt;
      </span>
      <label htmlFor="agent-input" className="sr-only">
        Ask anything about Manas
      </label>
      <input
        id="agent-input"
        type="text"
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        enterKeyHint="send"
        className="min-w-0 flex-1 border-0 bg-transparent px-0 py-1.5 text-text outline-none focus-visible:outline-none placeholder:text-faint"
      />
      <button
        type="submit"
        aria-label="Send message"
        disabled={disabled}
        className={`flex h-[38px] w-[38px] flex-none cursor-pointer items-center justify-center rounded-[var(--radius)] border transition-all duration-[var(--dur)] ease-[var(--ease)] disabled:cursor-not-allowed disabled:opacity-55 enabled:hover:border-border-hi enabled:hover:text-accent ${
          busy
            ? "animate-[sendpulse_1s_var(--ease)_infinite] border-accent bg-accent text-background opacity-100 shadow-[0_0_0_1px_var(--accent),0_0_22px_rgba(255,176,0,.55)]"
            : "border-border text-faint"
        }`}
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="m5 12 7-7 7 7" />
          <path d="M12 19V5" />
        </svg>
      </button>
    </form>
  );
}
