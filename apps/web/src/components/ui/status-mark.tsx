import type { ProjectStatus } from "@/lib/api/types";

const TONE: Record<ProjectStatus, string> = {
  completed: "text-ok",
  running: "text-accent",
  soon: "text-dim",
};

const MARK: Record<ProjectStatus, string> = {
  completed: "✔",
  running: "◐",
  soon: "◌",
};

/** Status line: `✔ completed`. Mark is semantic, not decorative. */
export function StatusMark({ status, label }: { status: ProjectStatus; label: string }) {
  return (
    <div className={`my-2 flex items-center gap-1.5 text-[0.86em] ${TONE[status]}`}>
      <span aria-hidden="true" className="w-[1.1em] text-center">
        {MARK[status]}
      </span>
      {label}
    </div>
  );
}
