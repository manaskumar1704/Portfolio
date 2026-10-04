"use client";

import { useEffect, useState } from "react";
import { CodeRain } from "./code-rain";
import { Slideshow, StaticRain } from "./slideshow";

type Variant = "code-rain" | "slideshow" | "none";

/** Hero background: `?bg=code-rain|slideshow|none`, static under reduced motion. */
export function AgentBackground() {
  const [variant, setVariant] = useState<Variant>("code-rain");
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    // deferred: state sync lives outside the effect body per lint rules
    const id = setTimeout(() => {
      setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
      const q = new URLSearchParams(window.location.search).get("bg");
      if (q === "slideshow" || q === "none") setVariant(q);
    }, 0);
    return () => clearTimeout(id);
  }, []);

  return (
    <div
      className="absolute inset-0 overflow-hidden bg-background"
      aria-hidden="true"
    >
      {variant === "none" ? null : reduced ? (
        <StaticRain />
      ) : variant === "slideshow" ? (
        <Slideshow />
      ) : (
        <CodeRain />
      )}
    </div>
  );
}
