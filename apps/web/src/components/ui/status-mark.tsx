import type { ProjectStatus } from "@/lib/api/types";

const STYLE: Record<ProjectStatus, { tone: string; mark: string }> = {
  completed: { tone: "text-ok", mark: "✔" },
  running: { tone: "text-accent", mark: "◐" },
  soon: { tone: "text-dim", mark: "◌" },
};

/** Status line: `✔ completed`. Mark is semantic, not decorative. */
export function StatusMark({ status, label }: { status: ProjectStatus; label: string }) {
  const { tone, mark } = STYLE[status];
  return (
    <div className={`my-2 flex items-center gap-1.5 text-[0.86em] ${tone}`}>
      <span aria-hidden="true" className="w-[1.1em] text-center">
        {mark}
      </span>
      {label}
    </div>
  );
}
