type SuggestionChipProps = {
  label: string;
  query: string;
  onAsk: (query: string) => void;
};

/** `[ ./projects ]` quick-prompt button. */
export function SuggestionChip({ label, query, onAsk }: SuggestionChipProps) {
  return (
    <button
      type="button"
      onClick={() => onAsk(query)}
      className="cursor-pointer whitespace-nowrap rounded-[var(--radius)] border border-border bg-[rgba(255,176,0,.04)] px-3 py-1.5 text-[0.88em] text-dim transition-colors duration-[var(--dur)] ease-[var(--ease)] hover:border-border-hi hover:bg-accent-soft hover:text-text focus-visible:border-accent focus-visible:outline-none focus-visible:shadow-[0_0_0_2px_rgba(255,176,0,.3)]"
    >
      <span className="text-accent">[</span> {label}{" "}
      <span className="text-accent">]</span>
    </button>
  );
}
