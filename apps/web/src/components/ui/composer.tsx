"use client";

import { useRef, useState } from "react";
import type { CommandEntry } from "@/lib/api/commands";
import { CommandMenu, filterCommands } from "./command-menu";

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
  /**
   * Entries for the `/` menu, like Claude Code: a bare `/` opens it, typing
   * narrows it, arrows pick, Enter/Tab inserts, Esc closes. Empty or omitted,
   * there is no menu.
   */
  commands?: CommandEntry[];
};

/** Prompt bar: `> input [↑]`. Turns amber while the agent is busy. */
export function Composer({
  value,
  busy,
  onValueChange,
  onSubmit,
  placeholder = "Ask anything about Manas…",
  commands = [],
}: ComposerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [active, setActive] = useState(0);
  const [hidden, setHidden] = useState(false);

  // A menu query is a leading slash with no word break yet — commands take no
  // arguments, so "/skills " closes it and free text never opens one.
  const query = value.startsWith("/") && !value.includes(" ") ? value : "";
  const items = query ? filterCommands(commands, query) : [];
  const open = query !== "" && items.length > 0 && !hidden;
  const selected = Math.min(active, Math.max(0, items.length - 1));

  /** Insert the picked command into the input; sending stays the user's move. */
  const select = (name: string) => {
    setHidden(false);
    setActive(0);
    onValueChange(`${name} `);
    // The caret lands after the inserted space, which only exists once React
    // commits the controlled value — hence trailing the commit by a frame.
    requestAnimationFrame(() => {
      const end = `${name} `.length;
      inputRef.current?.setSelectionRange(end, end);
    });
  };

  const disabled = value.trim().length === 0 || busy;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!disabled) onSubmit();
      }}
      className="relative mx-4 mb-4 mt-3 flex items-center gap-2.5 rounded-[var(--radius)] border border-border-hi bg-inset px-3.5 py-2 transition-colors duration-[var(--dur)] ease-[var(--ease)] focus-within:border-accent"
    >
      {open && <CommandMenu items={items} active={selected} onSelect={select} />}

      <span aria-hidden="true" className="flex-none text-accent">
        &gt;
      </span>
      <label htmlFor="agent-input" className="sr-only">
        Ask anything about Manas
      </label>
      <input
        ref={inputRef}
        id="agent-input"
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={open ? "agent-command-list" : undefined}
        aria-activedescendant={open ? `agent-command-option-${selected}` : undefined}
        aria-autocomplete="list"
        value={value}
        onChange={(e) => {
          setHidden(false);
          setActive(0);
          onValueChange(e.target.value);
        }}
        onKeyDown={(e) => {
          if (!open) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((current) => (current + 1) % items.length);
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((current) => (current - 1 + items.length) % items.length);
          } else if (e.key === "Escape") {
            // The typed text stays; the menu comes back on the next edit.
            setHidden(true);
          } else if (e.key === "Enter" || e.key === "Tab") {
            // Insert, don't send: the two-step matches every terminal palette,
            // and each command's send behaviour is already downstream.
            e.preventDefault();
            select(items[selected].name);
          }
        }}
        onFocus={() => setHidden(false)}
        onBlur={() => setHidden(true)}
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
