import { CONTACT } from "./contact";
import { PROJECTS } from "./projects";
import type { Project } from "./types";

/**
 * A node in the virtual filesystem the site is browsable as.
 *
 * Mirrors the shape a backend `GET /fs` would return, so swapping the fixtures
 * below for real fetches later only touches this file.
 */
export type FsDir = { type: "dir"; children: Record<string, FsNode> };
export type FsFile = { type: "file"; body: string };
export type FsNode = FsDir | FsFile;

/** A file's name is its body heading, so the node carries only the text. */
const file = (body: string): FsFile => ({ type: "file", body });

/** "GraphSAGE Fraud Detection" -> "graphsage-fraud-detection.md" */
const slug = (name: string): string =>
  name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

/** Project files reuse the project fixtures verbatim, so the text exists once. */
const projectBody = (p: Project): string =>
  [
    `# ${p.name}`,
    "",
    `status  ${p.label}`,
    `meta    ${p.meta}`,
    "",
    p.desc,
    "",
    `stack   ${p.stack}`,
  ].join("\n");

const ABOUT = [
  "# about",
  "",
  "Manas - GenAI & Full-Stack Engineer.",
  "",
  "He builds products where language models meet real software: retrieval that",
  "cites its sources, agents that stay in their lane, and interfaces that make",
  "the result legible.",
  "",
  "Works end to end - prompt and schema on one side, the button a person",
  "presses on the other.",
].join("\n");

const SKILLS = [
  "# skills",
  "",
  "languages   Python, TypeScript, Go, SQL, Bash",
  "genai/llm   RAG, agents, evals, pgvector",
  "frontend    React, Next.js, Tailwind",
  "backend     FastAPI, Node.js, Postgres, Redis",
  "infra       Docker, Kubernetes, AWS, Terraform, CI/CD",
].join("\n");

/**
 * The resume body, shared with the agent's scripted answer so the timeline
 * exists once. The `# resume` heading is added by the file, not carried here,
 * so a chat reply does not open with a markdown heading.
 */
export const RESUME = [
  "Manas — GenAI & Full-Stack Engineer.",
  "",
  "2023—now    Senior GenAI Engineer · Stealth AI Lab",
  "2021—2023   Full-Stack Engineer · Fintech Co",
  "2019—2021   Software Engineer · Software Studio",
  "",
  "Focus: grounded RAG, evals, and full-stack delivery.",
].join("\n");

const CONTACT_BODY = [
  "# contact",
  "",
  `email     ${CONTACT.email}`,
  `github    ${CONTACT.github}`,
  `linkedin  ${CONTACT.linkedin}`,
  "",
  CONTACT.note,
].join("\n");

export const FS: FsDir = {
  type: "dir",
  children: {
    "about.md": file(ABOUT),
    "skills.md": file(SKILLS),
    "resume.md": file(`# resume\n\n${RESUME}`),
    "contact.md": file(CONTACT_BODY),
    projects: {
      type: "dir",
      children: Object.fromEntries(
        PROJECTS.map((p) => [`${slug(p.name)}.md`, file(projectBody(p))]),
      ),
    },
  },
};

/**
 * Every path below the root, directories and files alike, as absolute paths.
 * Feeds `generateStaticParams` so each one is prerendered at build time.
 *
 * The root "/" is deliberately absent: it is served by `app/page.tsx`, and a
 * catch-all route never matches the bare path.
 */
export function allPaths(): string[] {
  const walk = (node: FsNode, path: string): string[] =>
    node.type === "file"
      ? [path]
      : [path, ...Object.entries(node.children).flatMap(([name, child]) => walk(child, `${path}/${name}`))];

  return Object.entries(FS.children).flatMap(([name, child]) =>
    walk(child, `/${name}`),
  );
}

/**
 * The node at a URL path, or null when nothing is there.
 *
 * Walks one segment at a time, so an intermediate hit on a file (asking for
 * "/about.md/skills.md") returns null instead of throwing. Empty segments from
 * a trailing slash are ignored, so "/projects/" and "/projects" agree.
 */
export function getNode(path: string): FsNode | null {
  let node: FsNode = FS;

  for (const segment of path.split("/")) {
    if (!segment) continue;
    if (node.type !== "dir") return null;
    const child: FsNode | undefined = node.children[segment];
    if (!child) return null;
    node = child;
  }

  return node;
}