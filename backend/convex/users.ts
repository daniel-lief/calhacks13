import { getAuthUserId } from "@convex-dev/auth/server";
import { ConvexError, v } from "convex/values";
import type { Id } from "./_generated/dataModel";
import { internalQuery, query, type MutationCtx } from "./_generated/server";

const USERNAME_RE = /^[a-z0-9_]{3,20}$/;
const RESERVED = new Set(["animai", "admin", "you", "me", "null", "undefined"]);

export function normalizeUsername(raw: string): string {
  return raw.trim().toLowerCase();
}

/** Why a (lowercased) username can't be used, or null if it's fine. */
export function usernameProblem(lower: string): string | null {
  if (!USERNAME_RE.test(lower)) return "Usernames are 3–20 characters: letters, numbers and _";
  if (RESERVED.has(lower)) return "That username is reserved";
  return null;
}

/** The signed-in user, or null. */
export const me = query({
  args: {},
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) return null;
    const user = await ctx.db.get(userId);
    if (!user) return null;
    return { _id: user._id, username: user.username ?? "", email: user.email ?? "" };
  },
});

/** The email behind a username or email, for signing in. Never exposed to clients. */
export const findForLogin = internalQuery({
  args: { identifier: v.string() },
  handler: async (ctx, { identifier }) => {
    const id = identifier.trim().toLowerCase();
    const user = id.includes("@")
      ? await ctx.db.query("users").withIndex("email", (q) => q.eq("email", id)).first()
      : await ctx.db.query("users").withIndex("by_usernameLower", (q) => q.eq("usernameLower", id)).first();
    if (!user || user.system || !user.email) return null;
    return { email: user.email };
  },
});

type CreateOrUpdateArgs = {
  existingUserId: Id<"users"> | null;
  profile: Record<string, unknown>;
};

/**
 * Convex Auth's user-creation callback. Runs inside one mutation, so checking that the
 * username and email are free and inserting the user can't race with another sign-up.
 */
export async function createOrUpdateUser(ctx: MutationCtx, args: CreateOrUpdateArgs): Promise<Id<"users">> {
  if (args.existingUserId !== null) return args.existingUserId;
  const email = String(args.profile.email ?? "").toLowerCase();
  const username = String(args.profile.username ?? "").trim();
  const usernameLower = normalizeUsername(username);
  const problem = usernameProblem(usernameLower);
  if (problem) throw new ConvexError(problem);
  const taken = await ctx.db
    .query("users")
    .withIndex("by_usernameLower", (q) => q.eq("usernameLower", usernameLower))
    .first();
  if (taken) throw new ConvexError("That username is taken");
  const emailUsed = await ctx.db.query("users").withIndex("email", (q) => q.eq("email", email)).first();
  if (emailUsed) throw new ConvexError("An account with that email already exists");
  return await ctx.db.insert("users", { email, username, usernameLower });
}
