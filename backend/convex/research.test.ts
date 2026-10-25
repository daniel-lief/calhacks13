import { expect, test } from "vitest";
import { api } from "./_generated/api";
import { addUser, as, makeTest } from "./test.utils";

const request = { topic: "Explain bubble sort", length: "short", quality: "low",
  narration: true, review: false, public: false, extra: "", voice: "", theme: "ocean" };

test("research defaults on, can be disabled, and reaches the worker", async () => {
  process.env.WORKER_SECRET = "research-test";
  const t = makeTest();
  const user = await addUser(t, "researcher");
  const id = await as(t, user).mutation(api.videos.create, request);
  const claimed = await t.mutation(api.worker.claimNext, { secret: "research-test" });
  expect(claimed?.id).toBe(id);
  expect(claimed?.options.research).toBe(true);
  const disabled = await as(t, user).mutation(api.videos.create, { ...request, research: false });
  expect((await as(t, user).query(api.videos.get, { id: disabled }))?.options.research).toBe(false);
});

test("research status and source links survive worker updates and live video queries", async () => {
  process.env.WORKER_SECRET = "research-test";
  const t = makeTest();
  const user = await addUser(t, "researcher");
  const id = await as(t, user).mutation(api.videos.create, request);
  await t.mutation(api.worker.update, { secret: "research-test", id, fields: {
    status: "researching", research: { status: "researching", message: "Reading transcripts", sources: [] },
  } });
  expect((await as(t, user).query(api.videos.get, { id }))?.status).toBe("researching");
  const report = { status: "ready" as const, message: "Read a transcript", cached: false,
    sources: [{ video_id: "aaaaaa00001", url: "https://www.youtube.com/watch?v=aaaaaa00001",
      title: "Bubble sort", channel: "Teacher", duration_seconds: 240, language: "en", auto_generated: false }] };
  await t.mutation(api.worker.update, { secret: "research-test", id, fields: { research: report } });
  expect((await as(t, user).query(api.videos.get, { id }))?.research).toEqual(report);
  expect(await t.query(api.videos.get, { id })).toBeNull();
});
