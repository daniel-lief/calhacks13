/// <reference types="vite/client" />
import { convexTest } from "convex-test";
import { describe, expect, test } from "vitest";
import { internal } from "./_generated/api";
import schema from "./schema";
import { createOrUpdateUser, normalizeUsername, usernameProblem } from "./users";

const modules = import.meta.glob("./**/*.ts");
const RULES = "Usernames are 3–20 characters: letters, numbers and _";

describe("username rules", () => {
  test("rejects bad shapes", () => {
    expect(usernameProblem("ab")).toBe(RULES);
    expect(usernameProblem("has space")).toBe(RULES);
    expect(usernameProblem("x".repeat(21))).toBe(RULES);
  });
  test("rejects reserved names", () => {
    expect(usernameProblem("admin")).toBe("That username is reserved");
    expect(usernameProblem("animai")).toBe("That username is reserved");
  });
  test("accepts a normal name", () => {
    expect(usernameProblem("bryce_01")).toBeNull();
  });
  test("normalizes case and whitespace", () => {
    expect(normalizeUsername("  Bryce ")).toBe("bryce");
  });
});

describe("findForLogin", () => {
  test("finds a user by username or email, case-insensitively, but never the system user", async () => {
    const t = convexTest(schema, modules);
    await t.run(async (ctx) => {
      await ctx.db.insert("users", { email: "b@x.com", username: "Bryce", usernameLower: "bryce" });
      await ctx.db.insert("users", { username: "animai", usernameLower: "animai", system: true });
    });
    expect(await t.query(internal.users.findForLogin, { identifier: "bryce" })).toEqual({ email: "b@x.com" });
    expect(await t.query(internal.users.findForLogin, { identifier: "BRYCE" })).toEqual({ email: "b@x.com" });
    expect(await t.query(internal.users.findForLogin, { identifier: "B@X.com" })).toEqual({ email: "b@x.com" });
    expect(await t.query(internal.users.findForLogin, { identifier: "nobody" })).toBeNull();
    expect(await t.query(internal.users.findForLogin, { identifier: "animai" })).toBeNull();
  });
});

describe("createOrUpdateUser", () => {
  const signUp = (username: string, email: string) => ({
    existingUserId: null,
    type: "credentials" as const,
    provider: { id: "password" } as never,
    profile: { email, username, usernameLower: normalizeUsername(username) },
  });

  test("a second sign-up with the same username in another case is rejected", async () => {
    const t = convexTest(schema, modules);
    await t.run((ctx) => createOrUpdateUser(ctx, signUp("Bryce", "one@x.com")));
    await expect(t.run((ctx) => createOrUpdateUser(ctx, signUp("bryce", "two@x.com")))).rejects.toThrow(
      "That username is taken",
    );
  });

  test("a second sign-up with the same email is rejected", async () => {
    const t = convexTest(schema, modules);
    await t.run((ctx) => createOrUpdateUser(ctx, signUp("first", "same@x.com")));
    await expect(t.run((ctx) => createOrUpdateUser(ctx, signUp("second", "same@x.com")))).rejects.toThrow(
      "An account with that email already exists",
    );
  });

  test("signing in to an existing account returns that user", async () => {
    const t = convexTest(schema, modules);
    const id = await t.run((ctx) => createOrUpdateUser(ctx, signUp("bryce", "b@x.com")));
    const again = await t.run((ctx) => createOrUpdateUser(ctx, { ...signUp("bryce", "b@x.com"), existingUserId: id }));
    expect(again).toBe(id);
  });
});
