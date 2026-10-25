import { authTables } from "@convex-dev/auth/server";
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export const STATUSES = ["queued", "researching", "writing", "checking", "rendering", "reviewing", "done", "failed"] as const;
export const ACTIVE_STATUSES = ["queued", "researching", "writing", "checking", "rendering", "reviewing"] as const;

export const videoOptions = v.object({
  length: v.string(),
  quality: v.string(),
  narration: v.boolean(),
  review: v.boolean(),
  research: v.optional(v.boolean()),
  extra: v.string(),
  voice: v.string(), // edge-tts voice name; "" means the server default
  theme: v.optional(v.string()), // color palette id from animai/assets/video-themes.json; absent means "bubble"
});

export const chapter = v.object({ start: v.number(), title: v.string() });

export const videoResearch = v.object({
  status: v.union(v.literal("researching"), v.literal("ready"), v.literal("partial"), v.literal("unavailable"), v.literal("skipped")),
  message: v.string(),
  cached: v.optional(v.boolean()),
  sources: v.array(v.object({
    video_id: v.string(), url: v.string(), title: v.string(), channel: v.string(),
    duration_seconds: v.number(), language: v.optional(v.string()), auto_generated: v.optional(v.boolean()),
  })),
});

export default defineSchema({
  ...authTables,

  // Convex Auth's users table, plus a unique username (stored lowercased for lookups)
  users: defineTable({
    name: v.optional(v.string()),
    image: v.optional(v.string()),
    email: v.optional(v.string()),
    emailVerificationTime: v.optional(v.number()),
    phone: v.optional(v.string()),
    phoneVerificationTime: v.optional(v.number()),
    isAnonymous: v.optional(v.boolean()),
    username: v.optional(v.string()),
    usernameLower: v.optional(v.string()),
    system: v.optional(v.boolean()), // @animai, owner of the samples; can't sign in
  })
    .index("email", ["email"])
    .index("by_usernameLower", ["usernameLower"]),

  videos: defineTable({
    owner: v.id("users"),
    topic: v.string(),
    options: videoOptions,
    status: v.union(...STATUSES.map((s) => v.literal(s))),
    stage: v.string(),
    progress: v.number(),
    research: v.optional(videoResearch),
    attempts: v.number(),
    title: v.optional(v.string()),
    error: v.optional(v.string()),
    model: v.optional(v.string()),
    costUsd: v.number(),
    tags: v.array(v.string()),
    chapters: v.array(chapter),
    public: v.boolean(),
    views: v.number(),
    likes: v.number(),
    files: v.object({
      video: v.optional(v.id("_storage")),
      thumbnail: v.optional(v.id("_storage")),
      captions: v.optional(v.id("_storage")),
      timings: v.optional(v.id("_storage")),
      code: v.optional(v.id("_storage")),
    }),
    startedAt: v.optional(v.number()),
    finishedAt: v.optional(v.number()),
    // One-time token for private PDF context held in the render server's memory. Erased when
    // the worker claims the video; never returned to clients.
    attachment: v.optional(v.string()),
  })
    .index("by_owner", ["owner"])
    .index("by_status", ["status"])
    .index("by_public_and_status", ["public", "status"]),

  // "Behind the scenes" lines, kept out of the video document so it stays small
  jobLogs: defineTable({
    video: v.id("videos"),
    t: v.number(),
    kind: v.string(),
    msg: v.string(),
  }).index("by_video", ["video"]),

  likes: defineTable({
    user: v.id("users"),
    video: v.id("videos"),
  })
    .index("by_user_and_video", ["user", "video"])
    .index("by_video", ["video"]),

  saves: defineTable({
    user: v.id("users"),
    video: v.id("videos"),
    savedAt: v.number(),
  })
    .index("by_user_and_video", ["user", "video"])
    .index("by_user_and_savedAt", ["user", "savedAt"])
    .index("by_video", ["video"]),
});
