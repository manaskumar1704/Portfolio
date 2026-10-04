import type { ReactNode } from "react";

/** Static fallback shown instead of the canvas under reduced motion. */
export function StaticRain() {
  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 overflow-hidden whitespace-pre p-6 text-[13px] leading-[1.4] text-[#5a6673]"
    >
      {"01001  $ whoami   10110  const agent = create()   00101\n11010  > ask --about manas   01101  await answer()"}
    </div>
  );
}

function Shot({
  title,
  className,
  children,
}: {
  title: string;
  /** Cross-fade offset, e.g. "[animation-delay:6s,0s]". */
  className: string;
  children: ReactNode;
}) {
  return (
    <div
      className={`absolute inset-[-5%] opacity-0 bg-inset animate-[sfade_24s_linear_infinite,skb_24s_linear_infinite] ${className}`}
    >
      <div className="flex items-center gap-1.5 border-b border-border px-3 py-2 text-[12px] text-faint">
        <i className="h-2.5 w-2.5 rounded-full bg-[#2a323c]" />
        <i className="h-2.5 w-2.5 rounded-full bg-[#2a323c]" />
        <i className="h-2.5 w-2.5 rounded-full bg-[#2a323c]" />
        <span className="ml-2">{title}</span>
      </div>
      {children}
    </div>
  );
}

/** Cross-fading fake project screenshots behind the console. */
export function Slideshow() {
  return (
    <div className="absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="slideshow absolute inset-0">
        <Shot title="agentflow — agent run" className="[animation-delay:0s,0s]">
          <div className="flex flex-col gap-2.5 px-[18px] py-4 text-[13px]">
            <span className="text-dim">
              <b className="font-normal text-accent">▸ </b>planning task graph…
            </span>
            <span className="text-dim">
              <b className="font-normal text-ok">✔ </b>3 agents spawned
            </span>
            <span className="text-dim">
              <b className="font-normal text-ok">✔ </b>shared memory synced ·
              1.2s
            </span>
          </div>
        </Shot>
        <Shot title="nimbus — analytics" className="[animation-delay:6s,0s]">
          <div className="grid grid-cols-3 gap-2.5 px-[18px] py-4">
            <div className="rounded-[var(--radius)] border border-border bg-panel p-2.5">
              <span className="block text-[18px] text-accent">1.4M</span>
              <span className="text-[11px] text-faint">events / day</span>
            </div>
            <div className="rounded-[var(--radius)] border border-border bg-panel p-2.5">
              <span className="block text-[18px] text-accent">280ms</span>
              <span className="text-[11px] text-faint">p50 query</span>
            </div>
            <div className="rounded-[var(--radius)] border border-border bg-panel p-2.5">
              <span className="block text-[18px] text-accent">99.9%</span>
              <span className="text-[11px] text-faint">uptime*</span>
            </div>
          </div>
        </Shot>
        <Shot title="graphsage — fraud graph" className="[animation-delay:12s,0s]">
          <div className="p-3">
            <svg
              viewBox="0 0 300 190"
              width="100%"
              height="190"
              role="img"
              aria-label="Abstract fraud-detection graph"
            >
              <g stroke="rgba(255,176,0,.35)" strokeWidth="1.2">
                <line x1="60" y1="60" x2="150" y2="95" />
                <line x1="150" y1="95" x2="240" y2="60" />
                <line x1="150" y1="95" x2="110" y2="150" />
                <line x1="150" y1="95" x2="205" y2="150" />
              </g>
              <g fill="#1b232c" stroke="#ffb000" strokeWidth="1.4">
                <circle cx="60" cy="60" r="13" />
                <circle cx="150" cy="95" r="17" />
                <circle cx="240" cy="60" r="12" />
                <circle cx="110" cy="150" r="14" />
                <circle cx="205" cy="150" r="12" />
              </g>
            </svg>
          </div>
        </Shot>
        <Shot title="portfolio chat" className="[animation-delay:18s,0s]">
          <div className="flex flex-col gap-2.5 px-[18px] py-4 text-[12.5px]">
            <div className="max-w-[78%] self-end rounded-lg border border-border bg-accent-soft px-3 py-2 text-text">
              What does Manas work on?
            </div>
            <div className="max-w-[78%] self-start rounded-lg border border-border bg-panel px-3 py-2 text-dim">
              Grounded LLM products — retrieval, evals, full-stack delivery.
            </div>
          </div>
        </Shot>
      </div>
      <div className="absolute inset-0 bg-[rgba(11,13,16,.72)]" />
    </div>
  );
}
