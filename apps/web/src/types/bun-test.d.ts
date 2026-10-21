/**
 * Ambient types for Bun's test runner.
 *
 * `AGENTS.md` forbids new dependencies without an ADR, so this declares the
 * handful of matchers we use instead of adding `@types/bun`. Tradeoff: tests are
 * checked against these signatures, not Bun's real ones. Drop this file and add
 * the devDependency if a matcher we need is missing.
 *
 * `not` is an object holding the same matchers, which is why the failure mode
 * here is a confusing "Property 'not' does not exist" rather than a type error
 * pointing at the assertion that is actually wrong.
 */
declare module "bun:test" {
  export function describe(name: string, fn: () => void): void;
  export function test(name: string, fn: () => void | Promise<void>): void;
  export function beforeEach(fn: () => void | Promise<void>): void;
  export function afterEach(fn: () => void | Promise<void>): void;

  interface Matchers {
    toBe(expected: unknown): void;
    toEqual(expected: unknown): void;
    toBeNull(): void;
    toBeUndefined(): void;
    toBeDefined(): void;
    toBeTruthy(): void;
    toBeFalsy(): void;
    toBeInstanceOf(constructor: unknown): void;
    toContain(needle: unknown): void;
    toHaveLength(length: number): void;
    toHaveProperty(path: string, value?: unknown): void;
    toMatch(pattern: RegExp | string): void;
    toBeGreaterThan(minimum: number): void;
    toBeLessThan(maximum: number): void;
    toThrow(expected?: unknown): void;
  }

  /** Negation. Same matchers, inverted. */
  interface Not {
    readonly not: Matchers;
  }

  export function expect(actual: unknown): Matchers & Not;
}