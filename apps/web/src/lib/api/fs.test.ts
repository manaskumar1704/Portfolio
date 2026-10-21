import { describe, expect, test } from "bun:test";
import { getNode } from "./fs";

describe("getNode", () => {
  test("the root is the whole filesystem", () => {
    expect(getNode("/")?.type).toBe("dir");
  });

  test("finds files at the root", () => {
    expect(getNode("/about.md")?.type).toBe("file");
  });

  test("finds directories and files inside them", () => {
    expect(getNode("/projects")?.type).toBe("dir");
    expect(getNode("/projects/agentflow.md")?.type).toBe("file");
  });

  test("returns null for anything absent", () => {
    expect(getNode("/nonsense")).toBeNull();
    expect(getNode("/projects/nope.md")).toBeNull();
  });

  test("does not walk through a file", () => {
    expect(getNode("/about.md/skills.md")).toBeNull();
  });

  test("ignores a trailing slash, so a shared link works either way", () => {
    expect(getNode("/projects/")?.type).toBe("dir");
  });
});