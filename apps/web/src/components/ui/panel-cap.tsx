type PanelCapProps = {
  label?: string;
  variant?: "top" | "bottom";
};

/** Box-drawing caption: `┌─ label ─── ─┐` / `└─── ─┘`. Pure decoration. */
export function PanelCap({ label, variant = "top" }: PanelCapProps) {
  const open = variant === "top" ? "┌─" : "└─";
  const close = variant === "top" ? "─┐" : "─┘";

  return (
    <div
      aria-hidden="true"
      className="flex select-none items-center whitespace-nowrap text-[0.9em] leading-none text-faint"
    >
      <span>{open}</span>
      {label ? (
        <>
          <span className="px-2 text-accent">{label}</span>
          <span>─</span>
        </>
      ) : null}
      <span className="mx-0.5 my-0 h-0 min-w-2.5 flex-1 self-center border-t border-border" />
      <span>{close}</span>
    </div>
  );
}
