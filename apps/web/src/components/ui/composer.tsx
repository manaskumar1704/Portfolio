"use client";

import { ArrowUp } from "lucide-react";

type ComposerProps = {
  value: string;
  busy: boolean;
  onValueChange: (value: string) => void;
  onSubmit: () => void;
};

/** Prompt bar: `> input [↑]`. Turns amber while the agent is busy. */
export function Composer({ value, busy, onValueChange, onSubmit }: ComposerProps) {
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
        placeholder="Ask anything about Manas…"
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
        <ArrowUp size={18} aria-hidden="true" />
      </button>
    </form>
  );
}
