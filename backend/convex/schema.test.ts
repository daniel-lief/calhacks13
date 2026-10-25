/// <reference types="vite/client" />
import { convexTest } from "convex-test";
import { expect, test } from "vitest";
import schema from "./schema";

const modules = import.meta.glob("./**/*.ts");

test("inserts a video with defaults", async () => {
  const t = convexTest(schema, modules);
  const video = await t.run(async (ctx) => {
    const owner = await ctx.db.insert("users", { email: "a@x.com", username: "a", usernameLower: "a" });
    const id = await ctx.db.insert("videos", {
      owner,
      topic: "Why ice floats",
      options: { length: "short", quality: "medium", narration: true, review: true, extra: "", voice: "" },
      status: "queued",
      stage: "Waiting in queue",
      progress: 0,
      attempts: 0,
      costUsd: 0,
      tags: [],
      chapters: [],
      public: true,
      views: 0,
      likes: 0,
      files: {},
    });
    return await ctx.db.get(id);
  });
  expect(video?.status).toBe("queued");
  expect(video?.files.video).toBeUndefined();
});

test("rejects a video with an unknown status", async () => {
  const t = convexTest(schema, modules);
  await expect(
    t.run(async (ctx) => {
      const owner = await ctx.db.insert("users", { email: "b@x.com" });
      await ctx.db.insert("videos", {
        owner,
        topic: "x",
        options: { length: "short", quality: "medium", narration: true, review: true, extra: "", voice: "" },
        status: "exploded" as never,
        stage: "",
        progress: 0,
        attempts: 0,
        costUsd: 0,
        tags: [],
        chapters: [],
        public: true,
        views: 0,
        likes: 0,
        files: {},
      });
    }),
  ).rejects.toThrow();
});
