"use client";

import { useState } from "react";
import { SuggestionChip } from "@/components/ui/suggestion-chip";
import { Typewriter } from "@/components/ui/typewriter";

/**
 * Shortcuts that open a path, the way an assistant's welcome screen does. Each
 * label is a real route, so middle-click and Back behave.
 */
const SUGGESTIONS = [
  { label: "./projects", href: "/projects" },
  { label: "./resume", href: "/resume.md" },
  { label: "./contact", href: "/contact.md" },
  { label: "./skills", href: "/skills.md" },
];

/**
 * Typed strictly in order: each line mounts only after the previous one calls
 * `onComplete`, so the sequence is sequential rather than parallel.
 */
const LINES = [
  { text: "whoami", speedMs: 78 },
  {
    text: "Manas — GenAI & Full-Stack Engineer",
    speedMs: 38,
    className:
      "min-h-[1.35em] text-[clamp(1.15rem,2.6vw,1.7rem)] font-semibold leading-[1.3] tracking-[0.01em] text-text",
  },
  {
    text: "I build grounded RAG, agents, and the full-stack products around them.",
    speedMs: 15,
    className:
      "min-h-[1.5em] max-w-[52ch] text-[0.95em] text-dim",
  },
];

/** ms between one line finishing and the next starting. */
const GAP_MS = 170;

type LandingProps = {
  dismissed: boolean;
};

/** Welcome layer: typewriter intro + path shortcuts. Zooms out on dismissal. */
export function Landing({ dismissed }: LandingProps) {
  const [step, setStep] = useState(0);
  const [gone, setGone] = useState(false);

  if (gone) return null;

  const next = (i: number) => setTimeout(() => setStep(i + 1), GAP_MS);

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
          {step >= 0 ? (
            <p className="min-h-[1.6em] text-dim">
              <span aria-hidden="true" className="text-accent">
                &gt;
              </span>{" "}
              <Typewriter
                text={LINES[0].text}
                speedMs={LINES[0].speedMs}
                onComplete={() => next(0)}
              />
            </p>
          ) : null}

          {step >= 1 ? (
            <p className={LINES[1].className}>
              <Typewriter
                text={LINES[1].text}
                speedMs={LINES[1].speedMs}
                onComplete={() => next(1)}
              />
            </p>
          ) : null}

          {step >= 2 ? (
            <p
              className={`animate-[msgin_520ms_var(--ease)_both] ${LINES[2].className}`}
            >
              <Typewriter
                text={LINES[2].text}
                speedMs={LINES[2].speedMs}
                onComplete={() => next(2)}
              />
            </p>
          ) : null}
        </div>

        <p className="max-w-[46ch] text-dim">
          Ask me anything in plain language — projects, resume, skills, or how
          to reach Manas. Slash commands work too: type <span className="text-text">/help</span>.
        </p>

        <div
          aria-label="Suggested questions"
          className="flex max-w-[620px] flex-wrap justify-center gap-2"
        >
          {SUGGESTIONS.map((s) => (
            <SuggestionChip
              key={s.label}
              label={s.label}
              href={s.href}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
