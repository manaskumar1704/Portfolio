"use client";

import { useEffect, useState } from "react";

const LINES = [
  "loading profile…",
  "mounting agent…",
  "indexing projects…",
  "ready — ask anything",
];

type Phase = "typing" | "fading" | "gone";

/** Boot sequence overlay: lines type in, any key/press skips, reduced motion skips. */
export function BootOverlay() {
  const [phase, setPhase] = useState<Phase>("typing");
  const [count, setCount] = useState(0);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      // deferred: state sync lives outside the effect body per lint rules
      const skip = setTimeout(() => setPhase("gone"), 0);
      return () => clearTimeout(skip);
    }

    const timers: ReturnType<typeof setTimeout>[] = [];
    const finish = () => {
      timers.forEach(clearTimeout);
      setPhase("fading");
      timers.push(setTimeout(() => setPhase("gone"), 260));
    };

    LINES.forEach((_, i) => {
      timers.push(setTimeout(() => setCount(i + 1), 280 * (i + 1)));
    });
    timers.push(setTimeout(finish, 280 * LINES.length + 360));

    window.addEventListener("keydown", finish);
    window.addEventListener("pointerdown", finish);
    return () => {
      timers.forEach(clearTimeout);
      window.removeEventListener("keydown", finish);
      window.removeEventListener("pointerdown", finish);
    };
  }, []);

  if (phase === "gone") return null;

  return (
    <div
      role="status"
      aria-label="Loading"
      className={`fixed inset-0 z-[200] flex items-center justify-center bg-background p-6 transition-opacity duration-[260ms] ${
        phase === "fading" ? "pointer-events-none opacity-0" : "opacity-100"
      }`}
    >
      <div className="w-[min(520px,100%)]">
        {LINES.slice(0, count).map((line) => (
          <div key={line} className="text-dim">
            <span className="text-ok">[ ok ] </span>
            {line}
          </div>
        ))}
        <p className="mt-3 text-[0.9em] text-faint">press any key to skip…</p>
      </div>
    </div>
  );
}
