import { describe, expect, test } from "vitest";
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
