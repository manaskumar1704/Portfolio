"use client";

/**
 * Where an answer came from.
 *
 * The whole point of the retrieval layer is that claims are grounded, so saying
 * which file answered is more persuasive than saying it confidently. A model
 * that is asked about a job title it has never been told will still answer
 * something; a citation tells the visitor which document to disbelieve.
 *
 * Rendered as a plain list of paths rather than links to GitHub. Linking out
 * means a corpus file could be edited after the answer was written, and the
 * citation would then point at something the visitor never saw. `source_path`
 * is what the retrieval actually matched, which is the honest thing to show.
 */

import type { Citation } from "@/lib/api/types";

export function Citations({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  return (
    <div className="cites">
      <span className="cites-label">from</span>
      <ul className="cites-list">
        {citations.map((citation) => (
          <li key={citation.sourcePath} className="cite">
            <span className="cite-file">{citation.label}</span>
            {citation.sourcePath !== citation.label && (
              <span className="cite-path">{citation.sourcePath}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}