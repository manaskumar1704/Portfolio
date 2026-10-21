"use client";

import { useEffect, useRef, useState } from "react";
import { Cursor } from "@/components/ui/cursor";
import { usePrefersReducedMotion } from "@/hooks/use-reduced-motion";

type TypewriterProps = {
  /** Full string to type. The component owns only how much of it is visible. */
  text: string;
  /** Milliseconds between characters. */
  speedMs?: number;
  /** Fired exactly once, after the last character lands. */
  onComplete?: () => void;
  /** Class applied to the text element. */
  className?: string;
};

/**
 * Types `text` one character at a time.
 *
 * One index is the only source of truth: the visible string is always
 * `text.slice(0, index)`. `index` runs 0..text.length inclusive and stops at
 * `text.length`, so the final character is rendered.
 */
export function Typewriter({
  text,
  speedMs = 40,
  onComplete,
  className,
}: TypewriterProps) {
  const reduced = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);

  // Latest callback, kept out of the effect deps so a new function identity on
  // every parent render cannot restart the timer.
  const latest = useRef(onComplete);
  useEffect(() => {
    latest.current = onComplete;
  });

  // `onComplete` must fire once per string, including under Strict Mode, which
  // invokes effects twice on mount.
  const fired = useRef(false);

  // Reset during render, not in an effect, so the timer below never fires once
  // with an index that belonged to the previous string.
  const [prevText, setPrevText] = useState(text);
  if (prevText !== text) {
    setPrevText(text);
    setIndex(0);
  }

  const complete = reduced || index >= text.length;

  useEffect(() => {
    if (complete) return;
    const id = setTimeout(() => setIndex((i) => i + 1), speedMs);
    return () => clearTimeout(id);
  }, [index, speedMs, complete]);

  // This effect owns the `fired` flag in both directions: typing (re)starting
  // rearms it, completing trips it. Doing it here rather than during render
  // keeps the flag off the render path, and arming it in the same effect keeps
  // Strict Mode's double-invoked mount from reporting completion twice.
  useEffect(() => {
    if (!complete) {
      fired.current = false;
      return;
    }
    if (fired.current) return;
    fired.current = true;
    latest.current?.();
  }, [complete, text]);

  return (
    <span className={className}>
      {reduced ? text : text.slice(0, index)}
      {complete ? null : <Cursor />}
    </span>
  );
}
