"use client";

import { Reveal } from "@/components/ui/reveal";
import { TaskCard } from "@/components/ui/task-card";
import { listProjects } from "@/lib/api/projects";
import { useAsync } from "@/lib/api/use-async";

function SectionHead({ index, title }: { index: string; title: string }) {
  return (
    <div className="mb-[22px] flex items-center gap-3">
      <span className="text-[0.9em] text-accent">{index}</span>
      <h2 className="m-0 text-[clamp(1.05rem,2.4vw,1.35rem)] font-medium tracking-[0.02em] text-text">
        {title}
      </h2>
      <span className="h-0 flex-1 border-t border-border" />
    </div>
  );
}

function Skeleton() {
  return (
    <div className="h-[168px] animate-pulse rounded-[var(--radius)] border border-border bg-panel" />
  );
}

/** Projects section: task cards with loading / empty / error states. */
export function ProjectsSection() {
  const { status, data, retry } = useAsync(listProjects);

  return (
    <section id="projects" className="scroll-mt-16 py-[clamp(44px,7vw,84px)]">
      <Reveal>
        <SectionHead index="01" title="agent tasks" />
      </Reveal>
      <Reveal>
        <p className="mb-[22px] max-w-[64ch] text-dim">
          Selected work, presented the way an agent reports its task queue.
          Status lines are illustrative. Ask the console above for the short
          version.
        </p>
      </Reveal>

      {status === "error" ? (
        <p className="text-err" role="alert">
          Failed to load projects.{" "}
          <button
            type="button"
            onClick={retry}
            className="cursor-pointer text-accent underline"
          >
            retry
          </button>
        </p>
      ) : status === "empty" ? (
        <p className="text-dim">No projects yet — check back soon.</p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
          {status === "loading"
            ? Array.from({ length: 3 }, (_, i) => <Skeleton key={i} />)
            : data?.map((project) => (
                <Reveal key={project.name} className="h-full">
                  <TaskCard project={project} />
                </Reveal>
              ))}
        </div>
      )}
    </section>
  );
}
