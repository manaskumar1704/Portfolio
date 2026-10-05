/**
 * Ambient types for Bun's test runner.
 *
 * `AGENTS.md` forbids new dependencies without an ADR, so this declares the
 * handful of matchers we use instead of adding `@types/bun`. Tradeoff: tests
 * are checked against these signatures, not Bun's real ones. Drop this file and
 * add the devDependency if a matcher we need is missing.
 */
declare module "bun:test" {
  export function describe(name: string, fn: () => void): void;
  export function test(name: string, fn: () => void | Promise<void>): void;

  interface Matchers {
    toBe(expected: unknown): void;
    toEqual(expected: unknown): void;
    toBeNull(): void;
    toBeUndefined(): void;
    toContain(needle: string): void;
    toHaveLength(length: number): void;
  }

  export function expect(actual: unknown): Matchers;
}