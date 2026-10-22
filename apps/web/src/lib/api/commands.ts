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
 * - `contact` — the `/contact` reply, plus one client side effect: the contact
 *   panel's message form opens. The boundary above still holds — a command
 *   opens a field that exists on this page; it does not navigate.
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

/contact — where to write (opens the message form)

/clear — start the conversation over

/compare-jd — coming soon; the service isn't wired yet

An answer never sends email by itself: a message becomes a draft that needs an explicit approval.`;

export type CommandOutcome =
  | { kind: "prompt"; message: string }
  | { kind: "reply"; message: string }
  /** `/contact` is a reply with one side effect: it opens the contact panel's
   *  message form (the hook dispatches the event). Still no navigation. */
  | { kind: "contact"; message: string }
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
    kind: "contact",
    message:
      "The message form is open in the contact panel below — Manas's address is " +
      "there too. A written message becomes a draft first: nothing is sent until " +
      "you approve it.",
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

/**
 * The composer's `/` menu, in display order. The same vocabulary as the table,
 * one line per command — a menu entry that says nothing is a menu entry with
 * something to hide, so every row here carries its own description.
 *
 * `commands.test.ts` pins the two invariants that keep this from rotting: every
 * advertised command resolves through `resolveCommand`, and the menu never
 * grows a command the table does not contain.
 */
export type CommandEntry = { name: string; description: string };

export const COMMAND_LIST: CommandEntry[] = [
  { name: "/skills", description: "his strongest skills, with sources" },
  { name: "/projects", description: "the projects and what each one does" },
  { name: "/resume", description: "recent roles and education" },
  { name: "/contact", description: "where to write — opens the message form" },
  { name: "/clear", description: "start the conversation over" },
  { name: "/help", description: "the command list, in the conversation" },
  { name: "/compare-jd", description: "coming soon — the service isn't wired yet" },
];
