import Link from "next/link";

/**
 * Routes, not `#anchor`s: the sections below the console on home are one view
 * of the site, and `/projects` is another. An anchor cannot survive a route
 * change, and the visitor's Back button has to keep working.
 */
const NAV = [
  { href: "/", label: "agent" },
  { href: "/projects", label: "projects" },
  { href: "/contact.md", label: "contact" },
];

export function Topbar() {
  return (
    <header className="sticky top-0 z-[80] flex items-center gap-4 border-b border-border bg-background/85 px-[clamp(14px,4vw,40px)] py-2.5 backdrop-blur-[8px]">
      <Link
        href="/"
        className="whitespace-nowrap font-medium text-text hover:text-accent hover:no-underline"
      >
        <span className="text-accent">$</span>{" "}
        <span className="max-[420px]:hidden">manas-dev</span>
      </Link>
      <nav
        aria-label="Sections"
        className="ml-auto flex flex-wrap gap-[clamp(8px,2vw,22px)]"
      >
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="whitespace-nowrap text-[0.92em] text-dim hover:text-accent hover:no-underline"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
