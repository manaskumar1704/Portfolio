import { SectionHead } from "@/components/ui/section-head";
import { getNode } from "@/lib/api/fs";
import { ListingRow } from "./listing-row";

/** Shared panel treatment for file bodies and the not-found message. */
const PRE =
  "m-0 overflow-x-auto whitespace-pre-wrap rounded-[var(--radius)] border border-border bg-panel p-4 text-[0.95em]";

/**
 * Renders whatever the URL points at: a directory listing, a file body, or the
 * "no file at" message for a path that does not exist.
 *
 * A Server Component on purpose. The file text and the listing arrive as HTML,
 * so browsing costs no extra client JavaScript.
 */
export function FsView({ path }: { path: string }) {
  const node = getNode(path);

  return (
    <section className="py-[clamp(44px,7vw,84px)]">
      <div className="mx-auto w-[min(1000px,100%)] px-[clamp(14px,4vw,40px)]">
        <SectionHead index="01" title={node === null ? "not found" : path} />

        {node === null ? (
          <pre className={`${PRE} text-text`}>{`error: no file at ${path}`}</pre>
        ) : node.type === "file" ? (
          <pre className={`${PRE} leading-relaxed text-dim`}>{node.body}</pre>
        ) : (
          <ul className="m-0 list-none overflow-hidden rounded-[var(--radius)] border border-border bg-panel p-1.5">
            {Object.entries(node.children)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([name, child]) => (
                <ListingRow
                  key={name}
                  href={`${path}/${name}`}
                  name={name}
                  isDir={child.type === "dir"}
                />
              ))}
          </ul>
        )}
      </div>
    </section>
  );
}