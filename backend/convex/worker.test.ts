import { beforeEach, describe, expect, test } from "vitest";
import { api } from "./_generated/api";
import { addUser, addVideo, makeTest } from "./test.utils";

const secret = "s3cret";
beforeEach(() => {
  process.env.WORKER_SECRET = secret;
});

const imported = {
  topic: "The Silk Road",
  title: "The Silk Road",
  options: { length: "short", quality: "medium", narration: true, review: true, extra: "", voice: "" },
  tags: ["history"],
  chapters: [{ start: 0, title: "Intro" }],
  public: true,
  views: 3,
  costUsd: 0.5,
  model: "claude-sonnet-5-5",
  files: {},
};

describe("worker API", () => {
  test("every worker function rejects the wrong secret", async () => {
    const t = makeTest();
    await expect(t.mutation(api.worker.claimNext, { secret: "nope" })).rejects.toThrow("Forbidden");
    await expect(t.mutation(api.worker.failStale, { secret: "nope" })).rejects.toThrow("Forbidden");
    await expect(t.mutation(api.worker.generateUploadUrl, { secret: "nope" })).rejects.toThrow("Forbidden");
  });

  test("claimNext hands out the oldest queued video, then nothing", async () => {
    const t = makeTest();
    const u = await addUser(t, "alice");
    const first = await addVideo(t, u, { status: "queued", topic: "first" });
    await addVideo(t, u, { status: "queued", topic: "second" });
    const job = await t.mutation(api.worker.claimNext, { secret });
    expect(job?.id).toBe(first);
    expect(job?.topic).toBe("first");
    const status = await t.run(async (ctx) => (await ctx.db.get(first))!.status);
    expect(status).toBe("writing");
    await t.mutation(api.worker.claimNext, { secret });
    expect(await t.mutation(api.worker.claimNext, { secret })).toBeNull();
  });

  test("update writes fields and keeps only the newest 300 log lines", async () => {
    const t = makeTest();
    const u = await addUser(t, "alice");
    const id = await addVideo(t, u, { status: "writing" });
    for (let i = 0; i < 305; i++) {
      await t.mutation(api.worker.update, { secret, id, fields: {}, log: { t: i, kind: "info", msg: `line ${i}` } });
    }
    await t.mutation(api.worker.update, { secret, id, fields: { stage: "Rendering", progress: 0.5 } });
    const state = await t.run(async (ctx) => ({
      video: await ctx.db.get(id),
      logs: await ctx.db.query("jobLogs").withIndex("by_video", (q) => q.eq("video", id)).collect(),
    }));
    expect(state.video?.stage).toBe("Rendering");
    expect(state.logs.length).toBe(300);
    expect(state.logs[0].msg).toBe("line 5");
  });

  test("failStale fails videos that were mid-render when the server stopped", async () => {
    const t = makeTest();
    const u = await addUser(t, "alice");
    const busy = await addVideo(t, u, { status: "rendering" });
    const done = await addVideo(t, u, { status: "done" });
    expect(await t.mutation(api.worker.failStale, { secret })).toBe(1);
    const after = await t.run(async (ctx) => ({ busy: await ctx.db.get(busy), done: await ctx.db.get(done) }));
    expect(after.busy?.status).toBe("failed");
    expect(after.busy?.error).toBe("The server restarted while this video was being made.");
    expect(after.done?.status).toBe("done");
  });

  test("attachFiles replaces files and deletes the ones it replaces", async () => {
    const t = makeTest();
    const u = await addUser(t, "alice");
    const id = await addVideo(t, u, { status: "rendering", withFile: false });
    const [one, two] = await t.run(async (ctx) => [
      await ctx.storage.store(new Blob(["first cut"])),
      await ctx.storage.store(new Blob(["polished cut"])),
    ]);
    await t.mutation(api.worker.attachFiles, { secret, id, files: { video: one } });
    await t.mutation(api.worker.attachFiles, { secret, id, files: { video: two } });
    const state = await t.run(async (ctx) => ({
      video: (await ctx.db.get(id))!.files.video,
      oldUrl: await ctx.storage.getUrl(one),
    }));
    expect(state.video).toBe(two);
    expect(state.oldUrl).toBeNull();
  });

  test("importVideo creates the @animai system user once and skips duplicates", async () => {
    const t = makeTest();
    const a = await t.mutation(api.worker.importVideo, { secret, ownerUsername: "animai", video: imported });
    const b = await t.mutation(api.worker.importVideo, { secret, ownerUsername: "animai", video: imported });
    expect(a.skipped).toBe(false);
    expect(b.skipped).toBe(true);
    const animais = await t.run((ctx) =>
      ctx.db.query("users").withIndex("by_usernameLower", (q) => q.eq("usernameLower", "animai")).collect(),
    );
    expect(animais.length).toBe(1);
    expect(animais[0].system).toBe(true);
  });

  test("importVideo needs an existing account for real users", async () => {
    const t = makeTest();
    await expect(
      t.mutation(api.worker.importVideo, { secret, ownerUsername: "ghost", video: imported }),
    ).rejects.toThrow("No account named @ghost");
  });
});
