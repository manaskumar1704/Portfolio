import type { Project } from "@/lib/api/types";
import { StatusMark } from "./status-mark";

/** Agent task card for one project. */
export function TaskCard({ project }: { project: Project }) {
  return (
    <article className="h-full rounded-[var(--radius)] border border-border bg-linear-180 from-panel to-[#0c1014] p-4 transition-all duration-[var(--dur)] ease-[var(--ease)] hover:-translate-y-0.5 hover:border-accent hover:shadow-[0_0_0_1px_rgba(255,176,0,.35),0_10px_34px_-14px_rgba(255,176,0,.4)]">
      <div className="flex items-baseline gap-2.5">
        <span className="text-[1.02em] font-bold text-text">{project.name}</span>
        <span className="ml-auto whitespace-nowrap text-[0.82em] text-faint">
          {project.meta}
        </span>
      </div>
      <StatusMark status={project.status} label={project.label} />
      <p className="mb-3 text-[0.94em] text-dim">{project.desc}</p>
      <div className="text-[0.86em] text-faint">
        <b className="font-medium text-dim">stack:</b> {project.stack}
      </div>
    </article>
  );
}
