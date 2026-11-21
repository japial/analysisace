import { describe, expect, it } from "vitest";

import bn from "../messages/bn.json";
import en from "../messages/en.json";

type Tree = { [key: string]: string | Tree };

function leaves(tree: Tree, prefix = ""): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out.set(path, value);
    else for (const [k, v] of leaves(value, path)) out.set(k, v);
  }
  return out;
}

function placeholders(message: string): string[] {
  return [...message.matchAll(/\{(\w+)[,}]/g)].map((m) => m[1] ?? "").sort();
}

const enLeaves = leaves(en);
const bnLeaves = leaves(bn);

describe("message files", () => {
  it("have the same keys in Bangla and English", () => {
    expect([...bnLeaves.keys()].sort()).toEqual([...enLeaves.keys()].sort());
  });

  it("have no empty strings", () => {
    for (const [key, value] of [...enLeaves, ...bnLeaves]) {
      expect(value.trim(), key).not.toBe("");
    }
  });

  it("use the same placeholders in both languages", () => {
    for (const [key, value] of enLeaves) {
      expect(placeholders(bnLeaves.get(key) ?? ""), key).toEqual(placeholders(value));
    }
  });

  it("carry the required disclaimer", () => {
    expect(en.common.disclaimer).toBe(
      "Historical analysis for education only. Not investment advice.",
    );
  });
});
