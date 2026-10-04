"use client";

import { useEffect, useState } from "react";
import { SuggestionChip } from "@/components/ui/suggestion-chip";

const SUGGESTIONS = [
  { label: "./projects", query: "Show me your projects" },
  { label: "./resume", query: "Walk me through your resume" },
  { label: "./contact", query: "How can I contact you?" },
  { label: "./skills", query: "What's your tech stack?" },
];

const LINES = [
  { text: "whoami", speed: 78 },
  {
    text: "Manas — GenAI & Full-Stack Engineer",
    speed: 38,
    className:
      "min-h-[1.35em] text-[clamp(1.15rem,2.6vw,1.7rem)] font-semibold leading-[1.3] tracking-[0.01em] text-text",
  },
  {
    text: "I build grounded RAG, agents, and the full-stack products around them.",
    speed: 15,
    className: "min-h-[1.5em] max-w-[52ch] text-[0.95em] text-dim",
  },
];

type LandingProps = {
  dismissed: boolean;
  onAsk: (query: string) => void;
};

/** Welcome layer: typewriter intro + suggestion chips. Zooms out on dismissal. */
export function Landing({ dismissed, onAsk }: LandingProps) {
  const [typed, setTyped] = useState(["", "", ""]);
  const [active, setActive] = useState(0);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    if (dismissed) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      // deferred: state sync lives outside the effect body per lint rules
      const skip = setTimeout(() => {
        setTyped(LINES.map((l) => l.text));
        setActive(-1);
      }, 0);
      return () => clearTimeout(skip);
    }

    let cancelled = false;
    let line = 0;
    let char = 0;
    let timer: ReturnType<typeof setTimeout>;

    const tick = () => {
      if (cancelled) return;
      const current = LINES[line];
      if (!current) return;
      char += 1;
      setTyped((prev) =>
        prev.map((t, i) => (i === line ? current.text.slice(0, char) : t)),
      );
      if (char < current.text.length) {
        timer = setTimeout(tick, current.speed);
      } else {
        line += 1;
        char = 0;
        setActive(line);
        timer = setTimeout(tick, 170);
      }
    };

    timer = setTimeout(tick, 240);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [dismissed]);

  if (gone) return null;

  return (
    <div
      onAnimationEnd={() => dismissed && setGone(true)}
      className={`absolute inset-0 z-[2] flex flex-col px-3.5 pb-4 pt-2 [transform-origin:center_center] ${
        dismissed
          ? "pointer-events-none animate-[landingOut_480ms_var(--ease)_both]"
          : ""
      }`}
    >
      <div className="flex items-center gap-2.5 px-0.5">
        <span
          aria-hidden="true"
          className="inline-block animate-[spin_3.4s_linear_infinite] text-accent [text-shadow:0_0_10px_rgba(255,176,0,.5)]"
        >
          ✳
        </span>
        <span className="font-medium text-text">
          manas <span className="font-normal text-faint">— agent</span>
        </span>
        <span className="ml-auto whitespace-nowrap rounded-full border border-border px-2.5 py-0.5 text-[0.78em] text-faint max-[640px]:hidden">
          natural language · scripted demo
        </span>
      </div>

      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-[18px] px-1.5 py-3 text-center">
        <div className="flex flex-col items-center gap-[3px]">
          <p className="min-h-[1.6em] text-dim">
            <span aria-hidden="true" className="text-accent">
              &gt;
            </span>{" "}
            {typed[0]}
            {active === 0 ? (
              <span
                aria-hidden="true"
                className="ml-0.5 animate-[blink_1s_steps(1)_infinite] text-accent"
              >
                ▋
              </span>
            ) : null}
          </p>
          <p className={LINES[1]?.className ?? ""}>
            {typed[1]}
            {active === 1 ? (
              <span
                aria-hidden="true"
                className="ml-0.5 animate-[blink_1s_steps(1)_infinite] text-accent"
              >
                ▋
              </span>
            ) : null}
          </p>
          <p className={LINES[2]?.className ?? ""}>
            {typed[2]}
            {active === 2 ? (
              <span
                aria-hidden="true"
                className="ml-0.5 animate-[blink_1s_steps(1)_infinite] text-accent"
              >
                ▋
              </span>
            ) : null}
          </p>
        </div>

        <p className="max-w-[46ch] text-dim">
          Ask me anything in plain language — projects, resume, skills, or how
          to reach Manas.
        </p>

        <div
          aria-label="Suggested questions"
          className="flex max-w-[620px] flex-wrap justify-center gap-2"
        >
          {SUGGESTIONS.map((s) => (
            <SuggestionChip
              key={s.label}
              label={s.label}
              query={s.query}
              onAsk={onAsk}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
