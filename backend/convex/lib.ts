import { getAuthUserId } from "@convex-dev/auth/server";
import { ConvexError } from "convex/values";
import type { Doc, Id } from "./_generated/dataModel";
import type { QueryCtx } from "./_generated/server";
import { ACTIVE_STATUSES } from "./schema";

export async function requireUser(ctx: QueryCtx): Promise<Id<"users">> {
  const userId = await getAuthUserId(ctx);
  if (userId === null) throw new ConvexError("Sign in first");
  return userId;
}

export function isActive(status: string): boolean {
  return (ACTIVE_STATUSES as readonly string[]).includes(status);
}

/** Whether `viewer` may see `video`: public and finished, or their own. */
export function canView(video: Doc<"videos">, viewer: Id<"users"> | null): boolean {
  return video.owner === viewer || (video.public && video.status === "done");
}

/** The video as the frontend uses it (the same shape the old JSON API returned, plus social fields). */
export async function toPublicVideo(ctx: QueryCtx, video: Doc<"videos">, viewer: Id<"users"> | null) {
  const owner = await ctx.db.get(video.owner);
  const url = async (id: Id<"_storage"> | undefined) => (id ? await ctx.storage.getUrl(id) : null);
  const mine = viewer !== null && viewer === video.owner;
  const liked =
    viewer !== null &&
    (await ctx.db
      .query("likes")
      .withIndex("by_user_and_video", (q) => q.eq("user", viewer).eq("video", video._id))
      .first()) !== null;
  const saved =
    viewer !== null &&
    (await ctx.db
      .query("saves")
      .withIndex("by_user_and_video", (q) => q.eq("user", viewer).eq("video", video._id))
      .first()) !== null;
  return {
    id: video._id,
    topic: video.topic,
    title: video.title ?? null,
    status: video.status,
    stage: video.stage,
    progress: video.progress,
    error: video.error ?? null,
    model: video.model ?? "",
    cost_usd: video.costUsd,
    options: video.options,
    tags: video.tags,
    chapters: video.chapters,
    public: video.public,
    views: video.views,
    likes: video.likes,
    created_at: video._creationTime / 1000,
    finished_at: video.finishedAt ? video.finishedAt / 1000 : null,
    has_video: video.files.video !== undefined,
    video_url: await url(video.files.video),
    thumbnail_url: await url(video.files.thumbnail),
    captions_url: await url(video.files.captions),
    timings_url: await url(video.files.timings),
    code_url: await url(video.files.code),
    voice: video.options.voice,
    author: { username: owner?.username ?? "unknown" },
    sample: owner?.system === true,
    ownedByMe: mine,
    likedByMe: liked,
    savedByMe: saved,
  };
}

export type PublicVideo = Awaited<ReturnType<typeof toPublicVideo>>;

const MAX_TAGS = 15;
const MAX_TAG_LENGTH = 24;

/** Lowercase, trimmed, de-duplicated, length-limited tags (same rules as backend/validate.py). */
export function cleanTags(tags: string[]): string[] {
  const out: string[] = [];
  for (const raw of tags) {
    const tag = raw.toLowerCase().split(/\s+/).filter(Boolean).join(" ").replace(/^#+/, "").trim().slice(0, MAX_TAG_LENGTH).trim();
    if (tag && !out.includes(tag)) out.push(tag);
  }
  return out.slice(0, MAX_TAGS);
}
