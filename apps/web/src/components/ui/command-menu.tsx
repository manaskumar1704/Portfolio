"use client";

import type { CommandEntry } from "@/lib/api/commands";

/**
 * The `/` menu, Claude-Code-style: what is typed narrows the list, arrows pick,
 * Enter or Tab inserts, and a click works too. Presentational on purpose — the
 * composer owns the input and the menu state; this only renders items and
 * answers a selection.
 *
 * `onMouseDown` rather than `onClick` so the caret never leaves the input: a
 * blur would close the menu between the two events.
 */
export function CommandMenu({
  items,
  active,
  onSelect,
}: {
  items: CommandEntry[];
  active: number;
  onSelect: (name: string) => void;
}) {
  return (
    <ul
      id="agent-command-list"
      role="listbox"
      aria-label="Available commands"
      className="absolute inset-x-0 bottom-full z-10 mb-1.5 max-h-52 overflow-y-auto rounded-[var(--radius)] border border-border-hi bg-inset p-1.5"
    >
      {items.map((item, index) => (
        <li
          key={item.name}
          id={`agent-command-option-${index}`}
          role="option"
          aria-selected={index === active}
          onMouseDown={(e) => {
            e.preventDefault();
            onSelect(item.name);
          }}
          className={`flex cursor-pointer items-baseline gap-2.5 rounded-[calc(var(--radius)-2px)] px-2.5 py-1.5 text-[0.92em] leading-relaxed transition-colors duration-[var(--dur)] ease-[var(--ease)] ${
            index === active ? "bg-accent-soft text-text" : "text-dim"
          }`}
        >
          <span className="flex-none text-accent">{item.name}</span>
          <span className="min-w-0 flex-1 truncate">{item.description}</span>
        </li>
      ))}
    </ul>
  );
}

/** Narrow the menu to what is typed. Case-insensitive from the start. */
export function filterCommands(items: CommandEntry[], typed: string): CommandEntry[] {
  const query = typed.toLowerCase();
  return items.filter((item) => item.name.toLowerCase().startsWith(query));
}
