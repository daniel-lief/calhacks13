import { getAuthUserId } from "@convex-dev/auth/server";
import { ConvexError, v } from "convex/values";
import type { Doc, Id } from "./_generated/dataModel";
import { mutation, query, type MutationCtx } from "./_generated/server";
import { canView, cleanTags, isActive, requireUser, toPublicVideo } from "./lib";

const LIST_LIMIT = 200;
const LOG_LIMIT = 300;

/** Public, finished videos, newest first. Anyone can read it. */
export const feed = query({
  args: {},
  handler: async (ctx) => {
    const viewer = await getAuthUserId(ctx);
    const rows = await ctx.db
      .query("videos")
      .withIndex("by_public_and_status", (q) => q.eq("public", true).eq("status", "done"))
      .order("desc")
      .take(LIST_LIMIT);
    const withVideo = rows.filter((v) => v.files.video !== undefined);
    return await Promise.all(withVideo.map((v) => toPublicVideo(ctx, v, viewer)));
  },
});

/** One video, or null if it doesn't exist or the viewer isn't allowed to see it. */
export const get = query({
  args: { id: v.id("videos") },
  handler: async (ctx, { id }) => {
    const viewer = await getAuthUserId(ctx);
    const video = await ctx.db.get(id);
    if (!video || !canView(video, viewer)) return null;
    return await toPublicVideo(ctx, video, viewer);
  },
});

/** Everything the signed-in user has made, newest first. */
export const myLibrary = query({
  args: {},
  handler: async (ctx) => {
    const viewer = await requireUser(ctx);
    const rows = await ctx.db
      .query("videos")
      .withIndex("by_owner", (q) => q.eq("owner", viewer))
      .order("desc")
      .take(LIST_LIMIT);
    return await Promise.all(rows.map((v) => toPublicVideo(ctx, v, viewer)));
  },
});

/** Public videos the signed-in user saved, most recently saved first. */
export const mySaved = query({
  args: {},
  handler: async (ctx) => {
    const viewer = await requireUser(ctx);
    const saves = await ctx.db
      .query("saves")
      .withIndex("by_user_and_savedAt", (q) => q.eq("user", viewer))
      .order("desc")
      .take(LIST_LIMIT);
    const videos = await Promise.all(saves.map((s) => ctx.db.get(s.video)));
    const visible = videos.filter((v): v is Doc<"videos"> => v !== null && canView(v, viewer));
    return await Promise.all(visible.map((v) => toPublicVideo(ctx, v, viewer)));
  },
});

/** The "Behind the scenes" log of one of your own videos (empty for anyone else). */
export const logs = query({
  args: { id: v.id("videos") },
  handler: async (ctx, { id }) => {
    const viewer = await getAuthUserId(ctx);
    const video = await ctx.db.get(id);
    if (!video || video.owner !== viewer) return [];
    const rows = await ctx.db
      .query("jobLogs")
      .withIndex("by_video", (q) => q.eq("video", id))
      .order("desc")
      .take(LOG_LIMIT);
    return rows.reverse().map((r) => ({ t: r.t, kind: r.kind, msg: r.msg }));
  },
});

// --- Social -------------------------------------------------------------------

/** Like or unlike a video you can see. Returns the new like count. */
export const like = mutation({
  args: { id: v.id("videos"), liked: v.boolean() },
  handler: async (ctx, { id, liked }) => {
    const viewer = await requireUser(ctx);
    const video = await ctx.db.get(id);
    if (!video || !canView(video, viewer)) throw new ConvexError("Video not found");
    const existing = await ctx.db
      .query("likes")
      .withIndex("by_user_and_video", (q) => q.eq("user", viewer).eq("video", id))
      .first();
    let likes = video.likes;
    if (liked && !existing) {
      await ctx.db.insert("likes", { user: viewer, video: id });
      likes += 1;
    } else if (!liked && existing) {
      await ctx.db.delete(existing._id);
      likes = Math.max(0, likes - 1);
    }
    if (likes !== video.likes) await ctx.db.patch(id, { likes });
    return { likes };
  },
});

/** Save someone else's public video to your library, or remove it. */
export const save = mutation({
  args: { id: v.id("videos"), saved: v.boolean() },
  handler: async (ctx, { id, saved }) => {
    const viewer = await requireUser(ctx);
    const video = await ctx.db.get(id);
    if (!video || !canView(video, viewer)) throw new ConvexError("Video not found");
    if (video.owner === viewer) throw new ConvexError("You can't save your own video");
    const existing = await ctx.db
      .query("saves")
      .withIndex("by_user_and_video", (q) => q.eq("user", viewer).eq("video", id))
      .first();
    if (saved && !existing) await ctx.db.insert("saves", { user: viewer, video: id, savedAt: Date.now() });
    if (!saved && existing) await ctx.db.delete(existing._id);
    return { saved };
  },
});

/** Count a view. Anyone can view a public video; owners can view their own. */
export const recordView = mutation({
  args: { id: v.id("videos") },
  handler: async (ctx, { id }) => {
    const viewer = await getAuthUserId(ctx);
    const video = await ctx.db.get(id);
    if (!video || !canView(video, viewer)) return null;
    await ctx.db.patch(id, { views: video.views + 1 });
    return null;
  },
});

// --- Owner edits ----------------------------------------------------------------

async function ownVideo(ctx: MutationCtx, id: Id<"videos">): Promise<Doc<"videos">> {
  const viewer = await requireUser(ctx);
  const video = await ctx.db.get(id);
  if (!video || video.owner !== viewer) throw new ConvexError("Video not found");
  return video;
}

export const setPublic = mutation({
  args: { id: v.id("videos"), public: v.boolean() },
  handler: async (ctx, args) => {
    await ownVideo(ctx, args.id);
    await ctx.db.patch(args.id, { public: args.public });
    return null;
  },
});

export const setTags = mutation({
  args: { id: v.id("videos"), tags: v.array(v.string()) },
  handler: async (ctx, { id, tags }) => {
    await ownVideo(ctx, id);
    const cleaned = cleanTags(tags);
    await ctx.db.patch(id, { tags: cleaned });
    return cleaned;
  },
});

/** Delete a finished or failed video, its files, logs, and everyone's likes and saves of it. */
export const remove = mutation({
  args: { id: v.id("videos") },
  handler: async (ctx, { id }) => {
    const video = await ownVideo(ctx, id);
    if (isActive(video.status)) throw new ConvexError("This video is still being made");
    for (const fileId of Object.values(video.files)) if (fileId) await ctx.storage.delete(fileId);
    for await (const row of ctx.db.query("jobLogs").withIndex("by_video", (q) => q.eq("video", id))) await ctx.db.delete(row._id);
    for await (const row of ctx.db.query("likes").withIndex("by_video", (q) => q.eq("video", id))) await ctx.db.delete(row._id);
    for await (const row of ctx.db.query("saves").withIndex("by_video", (q) => q.eq("video", id))) await ctx.db.delete(row._id);
    await ctx.db.delete(id);
    return null;
  },
});

// --- Creating -----------------------------------------------------------------

const DAILY_LIMIT = 100;
const DAY_MS = 24 * 60 * 60 * 1000;
const LENGTHS = ["short", "medium", "long"];
const QUALITIES = ["low", "medium", "high"];

/**
 * Queue a new video for the signed-in user. The render worker picks it up from here.
 * At most DAILY_LIMIT per user per rolling 24 hours.
 */
export const create = mutation({
  args: {
    topic: v.string(),
    length: v.string(),
    quality: v.string(),
    narration: v.boolean(),
    review: v.boolean(),
    public: v.boolean(),
    extra: v.string(),
    voice: v.string(),
  },
  handler: async (ctx, args) => {
    const owner = await requireUser(ctx);
    const topic = args.topic.split(/\s+/).filter(Boolean).join(" ");
    if (topic.length < 2 || topic.length > 300) throw new ConvexError("Topics need 2–300 characters");
    if (!LENGTHS.includes(args.length)) throw new ConvexError("Unknown length");
    if (!QUALITIES.includes(args.quality)) throw new ConvexError("Unknown quality");
    if (args.extra.length > 1000) throw new ConvexError("Guidance can be at most 1000 characters");

    const since = Date.now() - DAY_MS;
    let recent = 0;
    for await (const video of ctx.db.query("videos").withIndex("by_owner", (q) => q.eq("owner", owner)).order("desc")) {
      if (video._creationTime < since) break;
      if (++recent >= DAILY_LIMIT) {
        throw new ConvexError(`You've made ${DAILY_LIMIT} videos in the last 24 hours. Try again later.`);
      }
    }

    return await ctx.db.insert("videos", {
      owner,
      topic,
      options: {
        length: args.length,
        quality: args.quality,
        narration: args.narration,
        review: args.review,
        extra: args.extra.trim(),
        voice: args.voice,
      },
      status: "queued",
      stage: "Waiting in queue",
      progress: 0,
      attempts: 0,
      costUsd: 0,
      tags: [],
      chapters: [],
      public: args.public,
      views: 0,
      likes: 0,
      files: {},
    });
  },
});

/** 1 if this queued video is next up, 2 if one is ahead of it, and so on (0 if not queued). */
export const queuePosition = query({
  args: { id: v.id("videos") },
  handler: async (ctx, { id }) => {
    const video = await ctx.db.get(id);
    if (!video || video.status !== "queued") return 0;
    const queued = await ctx.db
      .query("videos")
      .withIndex("by_status", (q) => q.eq("status", "queued"))
      .take(1000);
    return queued.filter((v) => v._creationTime < video._creationTime).length + 1;
  },
});
