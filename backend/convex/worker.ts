// Functions the render worker (FastAPI on the team's machine) calls over Convex's HTTP API.
// Each takes the shared WORKER_SECRET, which lives only in the Convex deployment's
// environment and in backend/.env.local.
import { ConvexError, v } from "convex/values";
import type { Id } from "./_generated/dataModel";
import { mutation, type MutationCtx } from "./_generated/server";
import { ACTIVE_STATUSES, chapter, STATUSES, videoOptions, videoResearch } from "./schema";

const LOG_KEEP = 300;
const STALE_ERROR = "The server restarted while this video was being made.";

function checkSecret(secret: string) {
  const expected = process.env.WORKER_SECRET;
  if (!expected || secret !== expected) throw new ConvexError("Forbidden");
}

const fileIds = v.object({
  video: v.optional(v.id("_storage")),
  thumbnail: v.optional(v.id("_storage")),
  captions: v.optional(v.id("_storage")),
  timings: v.optional(v.id("_storage")),
  code: v.optional(v.id("_storage")),
});

/** Takes the oldest queued video and marks it started. */
export const claimNext = mutation({
  args: { secret: v.string() },
  handler: async (ctx, { secret }) => {
    checkSecret(secret);
    const next = await ctx.db
      .query("videos")
      .withIndex("by_status", (q) => q.eq("status", "queued"))
      .first();
    if (!next) return null;
    // The attachment token is handed over once and erased, so no trace of it stays with the video
    await ctx.db.patch(next._id, { status: "writing", stage: "Starting…", startedAt: Date.now(), attachment: undefined });
    return {
      id: next._id,
      topic: next.topic,
      options: next.options,
      attempts: next.attempts,
      attachment: next.attachment ?? null,
    };
  },
});

/** Progress, results and log lines from the pipeline. */
export const update = mutation({
  args: {
    secret: v.string(),
    id: v.id("videos"),
    fields: v.object({
      status: v.optional(v.union(...STATUSES.map((s) => v.literal(s)))),
      stage: v.optional(v.string()),
      research: v.optional(videoResearch),
      progress: v.optional(v.number()),
      attempts: v.optional(v.number()),
      title: v.optional(v.string()),
      tags: v.optional(v.array(v.string())),
      chapters: v.optional(v.array(chapter)),
      model: v.optional(v.string()),
      costUsd: v.optional(v.number()),
      error: v.optional(v.string()),
      finishedAt: v.optional(v.number()),
    }),
    log: v.optional(v.object({ t: v.number(), kind: v.string(), msg: v.string() })),
  },
  handler: async (ctx, { secret, id, fields, log }) => {
    checkSecret(secret);
    if (!(await ctx.db.get(id))) throw new ConvexError("Video not found");
    if (Object.keys(fields).length) await ctx.db.patch(id, fields);
    if (log) {
      await ctx.db.insert("jobLogs", { video: id, ...log });
      const rows = await ctx.db
        .query("jobLogs")
        .withIndex("by_video", (q) => q.eq("video", id))
        .take(LOG_KEEP + 50);
      for (const row of rows.slice(0, Math.max(0, rows.length - LOG_KEEP))) await ctx.db.delete(row._id);
    }
    return null;
  },
});

export const generateUploadUrl = mutation({
  args: { secret: v.string() },
  handler: async (ctx, { secret }) => {
    checkSecret(secret);
    return await ctx.storage.generateUploadUrl();
  },
});

/** Points the video at newly uploaded files, deleting any files they replace. */
export const attachFiles = mutation({
  args: { secret: v.string(), id: v.id("videos"), files: fileIds },
  handler: async (ctx, { secret, id, files }) => {
    checkSecret(secret);
    const video = await ctx.db.get(id);
    if (!video) throw new ConvexError("Video not found");
    for (const [name, newId] of Object.entries(files) as [keyof typeof files, Id<"_storage"> | undefined][]) {
      const oldId = video.files[name];
      if (newId && oldId && oldId !== newId) await ctx.storage.delete(oldId);
    }
    await ctx.db.patch(id, { files: { ...video.files, ...files } });
    return null;
  },
});

/** On worker startup: anything still "in progress" was interrupted, so mark it failed. */
export const failStale = mutation({
  args: { secret: v.string() },
  handler: async (ctx, { secret }) => {
    checkSecret(secret);
    let count = 0;
    for (const status of ACTIVE_STATUSES.filter((s) => s !== "queued")) {
      const rows = await ctx.db
        .query("videos")
        .withIndex("by_status", (q) => q.eq("status", status))
        .take(500);
      for (const row of rows) {
        await ctx.db.patch(row._id, { status: "failed", stage: "Failed", error: STALE_ERROR, finishedAt: Date.now() });
        count++;
      }
    }
    return count;
  },
});

async function ownerFor(ctx: MutationCtx, username: string): Promise<Id<"users">> {
  const lower = username.trim().toLowerCase();
  const user = await ctx.db
    .query("users")
    .withIndex("by_usernameLower", (q) => q.eq("usernameLower", lower))
    .first();
  if (user) return user._id;
  if (lower === "animai") return await ctx.db.insert("users", { username: "animai", usernameLower: "animai", system: true });
  throw new ConvexError(`No account named @${lower}`);
}

/** One-off import of an existing finished video (see backend/import_to_convex.py). */
export const importVideo = mutation({
  args: {
    secret: v.string(),
    ownerUsername: v.string(),
    video: v.object({
      topic: v.string(),
      title: v.optional(v.string()),
      options: videoOptions,
      tags: v.array(v.string()),
      chapters: v.array(chapter),
      public: v.boolean(),
      views: v.number(),
      costUsd: v.number(),
      model: v.optional(v.string()),
      files: fileIds,
    }),
  },
  handler: async (ctx, { secret, ownerUsername, video }) => {
    checkSecret(secret);
    const owner = await ownerFor(ctx, ownerUsername);
    const existing = await ctx.db
      .query("videos")
      .withIndex("by_owner", (q) => q.eq("owner", owner))
      .take(500);
    const dup = existing.find((v) => v.topic === video.topic && v.title === video.title);
    if (dup) {
      // Nothing new to store: drop the files that were uploaded for it
      for (const fileId of Object.values(video.files)) if (fileId) await ctx.storage.delete(fileId);
      return { id: dup._id, skipped: true };
    }
    const id = await ctx.db.insert("videos", {
      owner,
      ...video,
      status: "done",
      stage: "Done",
      progress: 1,
      attempts: 1,
      likes: 0,
      finishedAt: Date.now(),
    });
    return { id, skipped: false };
  },
});
