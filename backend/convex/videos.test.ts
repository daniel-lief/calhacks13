import { afterEach, describe, expect, test, vi } from "vitest";
import { api } from "./_generated/api";
import { addUser, addVideo, as, makeTest } from "./test.utils";

async function world() {
  const t = makeTest();
  const a = await addUser(t, "alice");
  const b = await addUser(t, "bob");
  const pub = await addVideo(t, a, { public: true, topic: "Public one" });
  const priv = await addVideo(t, a, { public: false, topic: "Private one" });
  return { t, a, b, pub, priv };
}

describe("reading videos", () => {
  test("the feed shows only public finished videos, even signed out", async () => {
    const { t } = await world();
    const feed = await t.query(api.videos.feed, {});
    expect(feed.map((v) => v.topic)).toEqual(["Public one"]);
    expect(feed[0].author.username).toBe("alice");
    expect(feed[0].video_url).toMatch(/^https?:/);
  });

  test("a private video is hidden from everyone but its owner", async () => {
    const { t, a, b, priv } = await world();
    expect(await t.query(api.videos.get, { id: priv })).toBeNull();
    expect(await as(t, b).query(api.videos.get, { id: priv })).toBeNull();
    const own = await as(t, a).query(api.videos.get, { id: priv });
    expect(own?.ownedByMe).toBe(true);
    expect(own?.topic).toBe("Private one");
  });

  test("the library needs sign-in and lists all of the owner's videos", async () => {
    const { t, a } = await world();
    const lib = await as(t, a).query(api.videos.myLibrary, {});
    expect(lib.map((v) => v.topic).sort()).toEqual(["Private one", "Public one"]);
    await expect(t.query(api.videos.myLibrary, {})).rejects.toThrow("Sign in first");
  });

  test("logs are only visible to the owner", async () => {
    const { t, a, b, pub } = await world();
    await t.run((ctx) => ctx.db.insert("jobLogs", { video: pub, t: 1, kind: "info", msg: "hello" }));
    expect(await as(t, b).query(api.videos.logs, { id: pub })).toEqual([]);
    expect((await as(t, a).query(api.videos.logs, { id: pub })).map((l) => l.msg)).toEqual(["hello"]);
  });
});

describe("social and owner actions", () => {
  test("liking is per user and idempotent, and needs sign-in", async () => {
    const { t, b, pub } = await world();
    await as(t, b).mutation(api.videos.like, { id: pub, liked: true });
    const twice = await as(t, b).mutation(api.videos.like, { id: pub, liked: true });
    expect(twice.likes).toBe(1);
    expect((await as(t, b).query(api.videos.get, { id: pub }))?.likedByMe).toBe(true);
    const undone = await as(t, b).mutation(api.videos.like, { id: pub, liked: false });
    expect(undone.likes).toBe(0);
    await expect(t.mutation(api.videos.like, { id: pub, liked: true })).rejects.toThrow("Sign in first");
  });

  test("you can't save your own video", async () => {
    const { t, a, pub } = await world();
    await expect(as(t, a).mutation(api.videos.save, { id: pub, saved: true })).rejects.toThrow(
      "You can't save your own video",
    );
  });

  test("deleting a video removes other people's saves and likes of it", async () => {
    const { t, a, b, pub } = await world();
    await as(t, b).mutation(api.videos.save, { id: pub, saved: true });
    await as(t, b).mutation(api.videos.like, { id: pub, liked: true });
    expect((await as(t, b).query(api.videos.mySaved, {})).length).toBe(1);
    await as(t, a).mutation(api.videos.remove, { id: pub });
    expect(await as(t, b).query(api.videos.mySaved, {})).toEqual([]);
    const leftovers = await t.run(async (ctx) => ({
      likes: (await ctx.db.query("likes").collect()).length,
      saves: (await ctx.db.query("saves").collect()).length,
    }));
    expect(leftovers).toEqual({ likes: 0, saves: 0 });
  });

  test("a video still being made can't be deleted", async () => {
    const { t, a } = await world();
    const busy = await addVideo(t, a, { status: "rendering" });
    await expect(as(t, a).mutation(api.videos.remove, { id: busy })).rejects.toThrow("This video is still being made");
  });

  test("tags are cleaned like the backend cleans them", async () => {
    const { t, a, pub } = await world();
    await as(t, a).mutation(api.videos.setTags, { id: pub, tags: ["Physics", " #Waves ", "physics"] });
    expect((await t.query(api.videos.get, { id: pub }))?.tags).toEqual(["physics", "waves"]);
  });

  test("only the owner can change visibility", async () => {
    const { t, a, b, pub } = await world();
    await expect(as(t, b).mutation(api.videos.setPublic, { id: pub, public: false })).rejects.toThrow(
      "Video not found",
    );
    await as(t, a).mutation(api.videos.setPublic, { id: pub, public: false });
    expect(await t.query(api.videos.get, { id: pub })).toBeNull();
  });

  test("views count for public videos, even signed out", async () => {
    const { t, pub } = await world();
    await t.mutation(api.videos.recordView, { id: pub });
    expect((await t.query(api.videos.get, { id: pub }))?.views).toBe(1);
  });
});

describe("creating videos", () => {
  const request = { topic: "Why ice floats", length: "short", quality: "medium", narration: true, review: true, public: true, extra: "", voice: "" };
  afterEach(() => vi.useRealTimers());

  test("needs sign-in", async () => {
    const { t } = await world();
    await expect(t.mutation(api.videos.create, request)).rejects.toThrow("Sign in first");
  });

  test("queues a video owned by the caller", async () => {
    const { t, b } = await world();
    const id = await as(t, b).mutation(api.videos.create, { ...request, topic: "  Why   ice floats " });
    const video = await as(t, b).query(api.videos.get, { id });
    expect(video?.status).toBe("queued");
    expect(video?.topic).toBe("Why ice floats");
    expect(video?.ownedByMe).toBe(true);
    expect(await as(t, b).query(api.videos.queuePosition, { id })).toBe(1);
  });

  test("rejects a too-short topic", async () => {
    const { t, b } = await world();
    await expect(as(t, b).mutation(api.videos.create, { ...request, topic: " a " })).rejects.toThrow(
      "Topics need 2–300 characters",
    );
  });

  test("allows 100 videos per rolling 24 hours", async () => {
    // convex-test never lets creation times go backwards, so set the clock before creating anything
    vi.useFakeTimers();
    const start = new Date("2026-10-24T12:00:00Z").getTime();
    vi.setSystemTime(start);
    const { t, b } = await world();
    for (let i = 0; i < 100; i++) await addVideo(t, b, { status: "done" });
    vi.setSystemTime(start + 60 * 60 * 1000);
    await expect(as(t, b).mutation(api.videos.create, request)).rejects.toThrow(
      "You've made 100 videos in the last 24 hours. Try again later.",
    );
    vi.setSystemTime(start + 25 * 60 * 60 * 1000);
    await expect(as(t, b).mutation(api.videos.create, request)).resolves.toBeTruthy();
  });
});
