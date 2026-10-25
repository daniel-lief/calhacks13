import { getAuthUserId } from "@convex-dev/auth/server";
import { v } from "convex/values";
import type { Doc } from "./_generated/dataModel";
import { query } from "./_generated/server";
import { canView, requireUser, toPublicVideo } from "./lib";

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
