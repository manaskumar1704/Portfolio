import Link from "next/link";

type SuggestionChipProps = {
  label: string;
  /** Route this chip opens. A real link, so middle-click and Back behave. */
  href: string;
};

/** `[ ./projects ]` shortcut that opens a path, the way a welcome screen does. */
export function SuggestionChip({ label, href }: SuggestionChipProps) {
  return (
    <Link
      href={href}
      className="whitespace-nowrap rounded-[var(--radius)] border border-border bg-[rgba(255,176,0,.04)] px-3 py-1.5 text-[0.88em] text-dim transition-colors duration-[var(--dur)] ease-[var(--ease)] hover:border-border-hi hover:bg-accent-soft hover:text-text focus-visible:border-accent focus-visible:outline-none focus-visible:shadow-[0_0_0_2px_rgba(255,176,0,.3)]"
    >
      <span className="text-accent">[</span> {label}{" "}
      <span className="text-accent">]</span>
    </Link>
  );
}