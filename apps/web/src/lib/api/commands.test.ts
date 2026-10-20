/**
 * Specification tests for `commands.ts`.
 *
 * The table is the whole feature, so the tests are about the table:
 * every command resolves, prompt expansions never look like commands when they
 * go back through the composer (or the re-resolution loop would recurse),
 * unknown commands are refused locally, and `/help` advertises exactly what
 * the table contains — that last one is what stops the help text rotting.
 */

import { describe, expect, test } from "bun:test";

import { COMMANDS_HELP, resolveCommand } from "./commands";
import type { CommandOutcome } from "./commands";

/** Expects `input` to resolve to kind `kind`, with real narrowing to match. */
function outcome<K extends CommandOutcome["kind"]>(
  input: string,
  kind: K,
): Extract<CommandOutcome, { kind: K }> {
  const resolved = resolveCommand(input);
  if (resolved === null || resolved === "unknown" || resolved.kind !== kind) {
    throw new Error(`expected ${input} to resolve as ${kind}, got ${String(resolved)}`);
  }
  // Narrowed by the guard above; TS cannot see through `resolved.kind !== kind`
  // into the union, so this says what the guard just proved.
  return resolved as Extract<CommandOutcome, { kind: K }>;
}

describe("resolveCommand", () => {
  test("the three prompt aliases expand to real questions", () => {
    for (const command of ["/skills", "/projects", "/resume"]) {
      const resolved = outcome(command, "prompt");
      expect(typeof resolved.message).toBe("string");
      expect(resolved.message.length).toBeGreaterThan(0);
    }
  });

  test("prompt expansions never look like commands when they come back", () => {
    // `send()` resolves, then sends the expansion: if the expansion started
    // with `/`, it would be re-resolved as a command on the way in.
    expect(outcome("/skills", "prompt").message.startsWith("/")).toBe(false);
    expect(outcome("/projects", "prompt").message.startsWith("/")).toBe(false);
    expect(outcome("/resume", "prompt").message.startsWith("/")).toBe(false);
  });

  test("the local commands are local", () => {
    expect(outcome("/contact", "reply").message.length).toBeGreaterThan(0);
    expect(outcome("/help", "reply").message.length).toBeGreaterThan(0);
    expect(resolveCommand("/clear")).toEqual({ kind: "clear" });
  });

  test("/compare-jd answers locally and points at /help", () => {
    expect(outcome("/compare-jd", "reply").message).toContain("/help");
  });

  test("the removed fs registry is refused like any unknown command", () => {
    // `ls`/`cd`/`cat` were removed from this app on purpose (frontend-plan §3):
    // no alias survives that removal, they are all plain "unknown".
    for (const command of ["/ls", "/cd", "/cat", "/fs"]) {
      expect(resolveCommand(command)).toBe("unknown");
    }
  });

  test("plain text is not a command", () => {
    expect(resolveCommand("What is AgentFlow?")).toBeNull();
    expect(resolveCommand("projects, please")).toBeNull();
    expect(resolveCommand("")).toBeNull();
    expect(resolveCommand("   ")).toBeNull();
  });

  test("a command matches on its first word, case-insensitively", () => {
    expect(outcome("/CLEAR now please", "clear")).toEqual({ kind: "clear" });
    expect(outcome("/HELP", "reply").message.length).toBeGreaterThan(0);
    expect(outcome("/Skills", "prompt").message.length).toBeGreaterThan(0);
  });
});

describe("COMMANDS_HELP", () => {
  test("lists every command the table contains", () => {
    for (const command of [
      "/skills",
      "/projects",
      "/resume",
      "/contact",
      "/compare-jd",
      "/clear",
    ]) {
      expect(COMMANDS_HELP).toContain(command);
    }
  });

  test("says nothing is sent without approval", () => {
    expect(COMMANDS_HELP).toContain("approval");
  });
});
