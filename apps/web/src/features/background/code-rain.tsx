"use client";

import { useEffect, useRef } from "react";

const GLYPHS = (
  "01{}[]()<>/\\=+-_$#@%&*;:.,~^|" + "abcdefghijklmnopqrstuvwxyz"
).split("");
const FS = 14;
const FRAME_MS = 70;

/** Matrix-style code rain over the hero. Animated canvas leaf. */
export function CodeRain() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let width = 0;
    let height = 0;
    let cols = 0;
    let drops: number[] = [];
    let raf = 0;
    let last = 0;

    const resize = () => {
      width = wrap.clientWidth || window.innerWidth;
      height = wrap.clientHeight || window.innerHeight;
      canvas.width = Math.max(1, width * dpr);
      canvas.height = Math.max(1, height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cols = Math.max(1, Math.ceil(width / FS));
      drops = Array.from(
        { length: cols },
        () => (Math.random() * -height) / FS,
      );
    };

    const frame = (t: number) => {
      raf = requestAnimationFrame(frame);
      if (t - last <= FRAME_MS) return;
      last = t;
      ctx.clearRect(0, 0, width, height);
      ctx.font = `${FS}px ${getComputedStyle(document.body).fontFamily}`;
      ctx.textBaseline = "top";
      for (let i = 0; i < cols; i++) {
        const x = i * FS;
        const y = drops[i]! * FS;
        ctx.fillStyle =
          Math.random() < 0.05
            ? "rgba(255,176,0,0.30)"
            : "rgba(150,165,180,0.10)";
        ctx.fillText(
          GLYPHS[Math.floor(Math.random() * GLYPHS.length)]!,
          x,
          y,
        );
        if (y > height && Math.random() > 0.975) drops[i] = 0;
        else drops[i] = (drops[i] ?? 0) + 0.5;
      }
    };

    resize();
    window.addEventListener("resize", resize);
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <div ref={wrapRef} className="absolute inset-0" aria-hidden="true">
      <canvas ref={canvasRef} className="block" />
    </div>
  );
}
