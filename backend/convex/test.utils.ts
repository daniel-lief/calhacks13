/// <reference types="vite/client" />
// Shared setup for the convex-test suites (not deployed as functions: it exports no Convex functions).
import { convexTest } from "convex-test";
import type { Id } from "./_generated/dataModel";
import schema from "./schema";

export const modules = import.meta.glob("./**/*.ts");

export function makeTest() {
  return convexTest(schema, modules);
}

export type T = ReturnType<typeof makeTest>;

export async function addUser(t: T, username: string, extra: { system?: boolean } = {}) {
  return await t.run((ctx) =>
    ctx.db.insert("users", {
      email: extra.system ? undefined : `${username}@x.com`,
      username,
      usernameLower: username.toLowerCase(),
      ...extra,
    }),
  );
}

export async function addVideo(
  t: T,
  owner: Id<"users">,
  fields: Partial<{ public: boolean; status: string; topic: string; withFile: boolean; createdAt: number }> = {},
) {
  return await t.run(async (ctx) => {
    const file = fields.withFile === false ? undefined : await ctx.storage.store(new Blob(["mp4"]));
    return await ctx.db.insert("videos", {
      owner,
      topic: fields.topic ?? "A topic",
      options: { length: "short", quality: "medium", narration: true, review: true, extra: "", voice: "" },
      status: (fields.status ?? "done") as never,
      stage: "Done",
      progress: 1,
      attempts: 1,
      costUsd: 0,
      title: fields.topic ?? "A topic",
      tags: ["physics", "waves", "light", "extra"],
      chapters: [{ start: 0, title: "Intro" }],
      public: fields.public ?? true,
      views: 0,
      likes: 0,
      files: { video: file },
    });
  });
}

/** Acting as a signed-in user (Convex Auth reads the user id from the identity subject). */
export function as(t: T, userId: Id<"users">) {
  return t.withIdentity({ subject: `${userId}|session`, tokenIdentifier: `test|${userId}` });
}
