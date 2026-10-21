"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

function Clock() {
  const [time, setTime] = useState("--:--");

  useEffect(() => {
    const tick = () =>
      setTime(
        `${String(new Date().getHours()).padStart(2, "0")}:${String(
          new Date().getMinutes(),
        ).padStart(2, "0")}`,
      );
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  return <span>{time}</span>;
}

export function Statusbar() {
  const path = usePathname();
  const folder = path === "/" ? "home" : path.replace(/^\//, "").replace(/\.md$/, "");

  return (
    <footer
      aria-hidden="true"
      className="fixed inset-x-0 bottom-0 z-[70] flex select-none items-center gap-3.5 border-t border-border bg-[rgba(10,12,15,.92)] px-[clamp(14px,4vw,40px)] py-1.5 text-[0.8em] text-dim backdrop-blur-[8px]"
    >
      <span>
        main <span className="text-ok">●</span> {folder}{" "}
        <span className="text-border-hi">|</span> v1.1
      </span>
      <span className="ml-auto flex gap-3.5 text-faint">
        <span className="max-[420px]:hidden">utf-8</span>
        <Clock />
      </span>
    </footer>
  );
}
