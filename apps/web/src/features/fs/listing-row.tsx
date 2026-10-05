import Link from "next/link";

type ListingRowProps = {
  /** Absolute path this entry points at. */
  href: string;
  /** Entry name. The row appends the "/" that marks a directory. */
  name: string;
  isDir: boolean;
};

/**
 * One line of the directory listing, wrapped in a real link so a path is
 * followable by clicking, middle-click or keyboard, not only by typing a URL.
 */
export function ListingRow({ href, name, isDir }: ListingRowProps) {
  return (
    <li>
      <Link
        href={href}
        className="flex items-baseline gap-3 rounded-[var(--radius)] px-3 py-1.5 hover:bg-inset hover:no-underline"
      >
        <span className="text-text">{isDir ? `${name}/` : name}</span>
        <span className="ml-auto text-faint">{isDir ? "dir" : "file"}</span>
      </Link>
    </li>
  );
}