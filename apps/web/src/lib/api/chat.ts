/**
 * The data-access seam. No fixtures for the agent any more.
 *
 * ## What changed
 *
 * This file used to hold a keyword-matching table of fake answers for
 * `about`, `resume`, `contact` and so on — including a hardcoded email address
 * and social links that were placeholders. That was fine while the backend did
 * not exist, and it is exactly the wrong thing to leave in place now: a
 * fixture that answers "here is his email" is a fixture that keeps answering
 * "here is his email" after the real one is wired up, in the one path nobody
 * tests.
 *
 * The transport lives in `./sse`. The parser and the approval handler are the two
 * files you are writing.
 *
 * ## What is still fixture-backed, and why that is fine
 *
 * `projects.ts`, `contact.ts` and `fs.ts` still hold typed fixtures. Those are
 * site content — the project list, the links, the résumé — not answers. They
 * are rendered from static files the site owns, and the real versions are
 * content, not API responses.
 *
 * If you later want them from the API, `useAsync` is the shape to copy and
 * `use-async.ts` already handles loading, empty and error.
 */

export { GREETING } from "@/features/agent/greeting";
export { ChatStreamError, pingHealth, streamChat } from "./sse";
export type { ChatRequest } from "./sse";