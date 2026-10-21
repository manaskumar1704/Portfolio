import type { ReactNode } from "react";

/** `key  value` output row from the contact.sh panel. */
export function ContactRow({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline gap-3.5">
      <span className="w-[9ch] flex-none text-dim max-[640px]:w-auto max-[640px]:text-faint">
        {k}
      </span>
      <span className="break-all text-text max-[640px]:flex-1">{children}</span>
    </div>
  );
}
