/**
 * The conversation's own command vocabulary.
 *
 * ## The boundary, from `docs/frontend-plan.md` §3
 *
 * Navigation is by link, never by typed command — none of these navigate. They
 * are prompt aliases and local replies in the chat's grammar:
 *
 * - `prompt` — expanded to the plain question it stands for, then down the
 *   normal streaming path like any other message, citations and all.
 * - `reply` — answered here in the browser with no LLM call, so the answer is
 *   never invented from nothing and costs nothing when the API is asleep.
 * - `clear` — local transcript reset.
 *
 * A command is matched on its first word only, case-insensitively; commands
 * take no arguments. Anything starting with `/` that is not in the table is
 * `unknown` — the composer answers that locally with the command list, so a
 * typo never becomes an LLM prompt.
 *
 * ## `/compare-jd` is a placeholder on purpose
 *
 * Comparing a job description against this portfolio belongs to the JobFinder
 * service (ADR 0008). Until it exists, the honest thing is a local reply that
 * says so and points at `/help` — an answer about a document the agent cannot
 * read would be exactly the confident-but-groundless reply this project exists
 * to avoid.
 *
 * Pure data: no DOM, no component tree — Bun tests run this file directly (the
 * project has no DOM test environment; adding one is an ADR).
 */

/** What `/help` prints. The contract: every table entry is listed here. */
export const COMMANDS_HELP = `Plain words work — answers come from Manas's own documents and cite the source.

/skills · /projects · /resume — answered, with sources

/contact — where to write

/clear — start the conversation over

/compare-jd — coming soon; the service isn't wired yet

An answer never sends email by itself: a message becomes a draft that needs an explicit approval.`;

export type CommandOutcome =
  | { kind: "prompt"; message: string }
  | { kind: "reply"; message: string }
  | { kind: "clear" };

/** `null`: not a command. `"unknown"`: starts with `/`, is not in the table. */
export type CommandResolution = CommandOutcome | "unknown" | null;

const TABLE: Readonly<Record<string, CommandOutcome>> = {
  "/skills": {
    kind: "prompt",
    message: "What are Manas's strongest skills, and where did he use them?",
  },
  "/projects": {
    kind: "prompt",
    message: "Which projects has Manas built, and what did each one actually do?",
  },
  "/resume": {
    kind: "prompt",
    message:
      "Walk me through Manas's resume — recent roles, education, and the skills he highlights.",
  },
  "/contact": {
    kind: "reply",
    message:
      "Manas's contact details are in the contact panel on the landing page. " +
      "Or ask me plainly — 'how can I reach Manas?' — and I'll answer with citations.",
  },
  "/compare-jd": {
    kind: "reply",
    message:
      "Comparing a job description against this portfolio isn't wired up yet — " +
      "it belongs to a service still being built, and I don't guess about " +
      "documents I can't read.\n\n" +
      "Ask me about the projects instead, or type /help for what works today.",
  },
  "/help": { kind: "reply", message: COMMANDS_HELP },
  "/clear": { kind: "clear" },
};

export function resolveCommand(input: string): CommandResolution {
  const word = input.trim().split(/\s+/, 1)[0]?.toLowerCase();
  if (!word?.startsWith("/")) return null;
  return TABLE[word] ?? "unknown";
}
