export type ProjectStatus = "completed" | "running" | "soon";

export type Project = {
  name: string;
  status: ProjectStatus;
  label: string;
  meta: string;
  desc: string;
  stack: string;
};

export type Contact = {
  email: string;
  github: string;
  linkedin: string;
  note: string;
};

export type ChatRole = "user" | "bot";

export type ChatMessage = {
  id: number;
  role: ChatRole;
  text: string;
  /** true while the agent shows its "thinking" indicator */
  thinking?: boolean;
  /** Sources this answer is grounded in, in the order they were first cited. */
  citations?: Citation[];
  /**
   * Whether this turn's answer was actually verified. Absent on every message
   * that has not finished, and false is the honest value for this release: no
   * verifier is wired, so the badge stays dark. Renders only on true.
   */
  sourcesVerified?: boolean;
};

/** A retrieved corpus chunk an answer is grounded in. */
export type Citation = {
  /** e.g. "resume.md" — display only. */
  label: string;
  /** The path the chunk came from, e.g. "projects/agentflow.md". */
  sourcePath: string;
};

/**
 * One SSE frame from `POST /chat`.
 *
 * Mirrors `app/services/chat.py`. `delta` is the only kind that arrives many
 * times per answer; the rest arrive at most once each.
 *
 * The wire format is snake_case and this is camelCase. The parser is the one
 * place that knows, so nothing downstream has to.
 *
 * `unknown` is in the union on purpose: a backend may add an event without
 * breaking an older frontend, and the parser must return it rather than throw
 * or drop it silently.
 */
export type ChatEvent =
  | { kind: "delta"; text: string }
  | { kind: "tool_call"; id: string; name: string; arguments: string }
  | { kind: "tool_result"; id: string; name: string; ok: boolean; error: string | null }
  | { kind: "citation"; sourcePath: string; label: string }
  | {
      kind: "draft";
      id: number;
      name: string;
      email: string;
      body: string;
      /** The send capability. Never stored, never rendered, never logged. */
      approvalToken: string;
      expiresAt: string;
    }
  | { kind: "busy"; retryAfterSeconds: number; message: string }
  | { kind: "error"; message: string }
  | {
      kind: "done";
      sources: string[];
      textLength: number;
      /**
       * The badge's contract field. `false` is meaningful, not absent: it says
       * nothing earned verification this turn, which is the honest value until
       * a verifier is wired (services/verify.py). The badge renders only on
       * true.
       */
      sourcesVerified: boolean;
    }
  | { kind: "unknown"; name: string; data: unknown };

/** A drafted message awaiting the visitor's approval. */
export type Draft = {
  id: number;
  name: string;
  email: string;
  body: string;
  expiresAt: string;
};

/**
 * Why an approval did not go through.
 *
 * A union rather than a status code, because three of these want different
 * words in the UI and "something went wrong" is none of them.
 */
export type SendFailure =
  /** 403 — wrong token, wrong IP, or no such message. The server returns the
   *  same body for all three, deliberately, so this cannot be narrowed. */
  | "refused"
  /** 409 — already sent, or a concurrent request won the race. */
  | "already"
  /** 410 — the draft expired. Write it again. */
  | "expired"
  /** 429 — the owner's daily send cap. Try tomorrow. */
  | "cap"
  /** 503 — email is not configured on the server. */
  | "unavailable"
  /** No response at all: asleep, deploying, or offline. */
  | "network";

export type SendResult = { ok: true } | { ok: false; reason: SendFailure; message: string };

/** Everything the composer can be in. */
export type AgentStatus =
  /** Nothing typed, no API contact. */
  | "idle"
  /** Render slept; `/health` has not answered. Not an error, and not shown as one. */
  | "waking"
  /** Request sent, no token yet. */
  | "thinking"
  /** Tokens arriving. */
  | "streaming"
  /** Answer complete. */
  | "done"
  /** 429 — too many questions. */
  | "busy"
  | "error";