type SectionHeadProps = {
  /** Two-digit section index, e.g. "01". */
  index: string;
  title: string;
};

/** `01  title ————` section header with a hairline rule. */
export function SectionHead({ index, title }: SectionHeadProps) {
  return (
    <div className="mb-[22px] flex items-center gap-3">
      <span className="text-[0.9em] text-accent">{index}</span>
      <h2 className="m-0 text-[clamp(1.05rem,2.4vw,1.35rem)] font-medium tracking-[0.02em] text-text">
        {title}
      </h2>
      <span className="h-0 flex-1 border-t border-border" />
    </div>
  );
}