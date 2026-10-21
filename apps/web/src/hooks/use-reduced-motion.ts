"use client";

import { useSyncExternalStore } from "react";

/** The reduced-motion media query. Exported for the one-shot mount reads. */
export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

const QUERY = REDUCED_MOTION_QUERY;

function subscribe(onChange: () => void) {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

const read = () => window.matchMedia(QUERY).matches;

/**
 * True when the user asked for reduced motion.
 *
 * Subscribing to the media query rather than reading it into state means no
 * setState-in-effect, and a mid-session change to the OS setting is picked up.
 */
export function usePrefersReducedMotion() {
  return useSyncExternalStore(subscribe, read, () => false);
}