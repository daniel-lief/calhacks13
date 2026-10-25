# Convex Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Animai's data, video files and accounts from local JSON files into Convex, with real email/username sign-in, while FastAPI keeps doing Claude + rendering as a worker.

**Architecture:** Convex (cloud deployment `majestic-civet-774`, functions in `backend/convex/`) becomes the source of truth for users, videos, logs, likes, saves and all media files. The browser talks to Convex directly through its script-tag client (live queries, no build step). FastAPI no longer receives "make a video" requests: the browser creates a `queued` video in Convex, and a worker loop inside FastAPI polls Convex over its HTTP API, claims the job, runs the existing Claude/render pipeline, and writes progress and files back to Convex using a shared secret.

**Tech Stack:** Convex 1.48 (TypeScript functions), `@convex-dev/auth` (Password + ConvexCredentials providers), `convex-test` + `vitest` for function tests; Python 3.11 FastAPI with `httpx` (already installed via `anthropic`) and stdlib `unittest`; plain-JS frontend using `convex/dist/browser.bundle.js` from unpkg.

**Spec:** the decisions agreed in conversation on 2026-10-24, restated in "Agreed decisions" below. This file is the spec.

## Agreed decisions

1. Sign-up needs **username, email and password**. Sign-in accepts **username or email** plus password.
2. Usernames are unique, case-insensitive, 3–20 characters of `a-z 0-9 _`, displayed as `@name`. Reserved: `animai`, `admin`, `you`, `me`, `null`, `undefined`.
3. Passwords are at least 8 characters. Failed sign-in always says exactly: `Wrong username, email or password`.
4. No email verification and no password reset (no email service).
5. Logged-out visitors can browse the feed, Scroll and watch pages. They cannot create, like or save videos.
6. Any signed-in user can generate videos, **at most 100 per rolling 24 hours** per account.
7. Existing data is imported: the six samples under a system user `@animai` (no password, cannot sign in), the user's own videos under their account (they sign up first).
8. Private videos are visible only to their owner. Only the owner can change visibility, edit tags or delete. You can't save your own video.
9. Edits stay inside `frontend/` and `backend/` (the user's standing rule). Rendering, Claude, tags, chapters and voices behave exactly as today.

## Global Constraints

- Only modify files under `frontend/` and `backend/`. Do not touch `animai/`, `animlib/`, `gallery/`, `requirements.txt` or root files. No new Python packages.
- Convex functions follow `backend/convex/_generated/ai/guidelines.md` (read it before Task 1): argument validators on every function, `internal*` for private functions, identity derived server-side with `getAuthUserId`, never taken from arguments.
- `WORKER_SECRET` is a Convex environment variable (`npx convex env set`) and a line in `backend/.env.local`. It never goes in git, logs or API responses.
- `backend/.env.local` holds `CONVEX_URL`, `CONVEX_DEPLOYMENT`, `WORKER_SECRET`. `backend/config.py` loads it in addition to the root `.env`.
- Keep the frontend's look, screens and copy. Only data access changes, plus the new sign-in UI.
- Run Convex commands from `backend/` (`npx convex dev --once` to deploy functions during work).

## Review Focus

1. **Signed-out user presses Like, Save or Generate:** the action must not run, and the sign-in screen opens. The mutations also reject with `Sign in first`. (Task 3 test, Task 10 check)
2. **Username typed in a different case at sign-in or sign-up** (`Bryce` vs `bryce`): sign-in works, and the duplicate sign-up is rejected as taken. (Task 2 tests)
3. **Worker crashes or the laptop restarts mid-render:** the video must not stay "rendering" forever. On startup the worker marks the owner's stuck videos `failed` with `The server restarted while this video was being made.` (Task 6 test)
4. **Opening a private video's watch link while signed out or as another user:** shows "This video isn't available", never the video. (Task 3 test)
5. **Deleting a video someone else saved or liked:** their library and like counts must not break; the save and like rows are removed with the video. (Task 4 test)

---

## File map

| File | Responsibility |
|---|---|
| `backend/convex/schema.ts` | Tables and indexes |
| `backend/convex/auth.ts`, `auth.config.ts`, `http.ts` | Convex Auth setup, providers, routes |
| `backend/convex/users.ts` | Username rules, `me`, lookups |
| `backend/convex/videos.ts` | Public reads (feed, get, library, saved) and owner/social mutations |
| `backend/convex/worker.ts` | Secret-guarded functions the render worker calls |
| `backend/convex/lib.ts` | Shared helpers: `toPublicVideo`, `requireUser`, `checkSecret` |
| `backend/convex/*.test.ts` | convex-test suites |
| `backend/convex_api.py` | Python client for Convex's HTTP API and file uploads |
| `backend/worker.py` | Polling loop: claim, run pipeline, report |
| `backend/jobs.py` | Pipeline steps, now writing to Convex instead of JSON |
| `backend/import_to_convex.py` | One-off import of samples and existing videos |
| `backend/app.py` | Serves the site, `/api/config`, `/api/health`, voices; starts the worker |
| `frontend/convex.js` | Convex client, session tokens, sign-in/out, `call`/`watch` helpers |
| `frontend/auth.js` | Sign-in / sign-up screen and the sidebar account area |
| `frontend/*.js` (existing) | Switch from `/api/...` fetches to Convex |

---

### Task 1: Convex tooling, test harness and schema

**Files:**
- Modify: `backend/package.json` (dev deps and `"test": "vitest run"`)
- Create: `backend/vitest.config.ts`, `backend/convex/schema.test.ts`
- Modify: `backend/convex/schema.ts`

**Interfaces:**
- Produces tables (all through `defineSchema`):
  - `...authTables`, with `users` overridden to add `username: v.optional(v.string())`, `usernameLower: v.optional(v.string())` and `system: v.optional(v.boolean())`. Indexes: `email` (from authTables) and `by_usernameLower`.
  - `videos`:
    - `owner: v.id("users")`
    - `topic: v.string()`
    - `options: v.object({ length, quality, narration: v.boolean(), review: v.boolean(), extra: v.string(), voice: v.string() })`
    - `status: v.union(...["queued","writing","checking","rendering","reviewing","done","failed"].map(v.literal))`
    - `stage: v.string()`, `progress: v.number()`, `attempts: v.number()`
    - `title`, `error`, `model` (optional strings), `costUsd: v.number()`
    - `tags: v.array(v.string())`
    - `chapters: v.array(v.object({ start: v.number(), title: v.string() }))`
    - `public: v.boolean()`, `views: v.number()`, `likes: v.number()`
    - `files: v.object({ video, thumbnail, captions, timings, code })`, each `v.optional(v.id("_storage"))`
    - `startedAt`, `finishedAt` (optional numbers)
    - Indexes: `by_owner` `["owner"]`, `by_status` `["status"]`, `by_public` `["public","status"]`
  - `jobLogs`: `video: v.id("videos")`, `t: v.number()`, `kind: v.string()`, `msg: v.string()`. Index `by_video`.
  - `likes`: `user: v.id("users")`, `video: v.id("videos")`. Indexes `by_user_video`, `by_video`.
  - `saves`: `user`, `video`, `savedAt: v.number()`. Indexes `by_user_video`, `by_user` `["user","savedAt"]`, `by_video`.

- [ ] **Step 1:** In `backend/`, install `npm i @convex-dev/auth jose` and `npm i -D convex-test vitest @edge-runtime/vm`. Add `vitest.config.ts` with `environment: "edge-runtime"` and `server.deps.inline: ["convex-test"]`.
- [ ] **Step 2: Write the failing test** `schema.test.ts › "inserts a video with defaults"`: using `convexTest(schema, modules)`, insert a user and a `videos` row with `status: "queued"`, empty tags, chapters and files, then read it back. Assert `status === "queued"` and `files.video === undefined`.
- [ ] **Step 3:** Run `npm test` and expect it to fail, because the `videos` table doesn't exist.
- [ ] **Step 4:** Write the schema above.
- [ ] **Step 5:** Run `npm test` and expect PASS. Run `npx convex dev --once` and expect "Convex functions ready".
- [ ] **Step 6: Commit** `feat(convex): schema and test harness`.

### Task 2: Accounts (username or email sign-in)

**Files:**
- Create: `backend/convex/auth.ts`, `backend/convex/auth.config.ts`, `backend/convex/http.ts`, `backend/convex/users.ts`, `backend/convex/auth.test.ts`

**Interfaces:**
- `users.ts`:
  - `normalizeUsername(raw: string): string` (trimmed, lowercased).
  - `usernameProblem(lower: string): string | null` returns exactly one of:
    - `Usernames are 3–20 characters: letters, numbers and _`
    - `That username is reserved`
    - `null`
  - `query me` returns `{ _id, username, email } | null`.
  - `internalQuery findForLogin({ identifier })` returns `{ email } | null`. It looks up by email (lowercased) if the identifier contains `@`, otherwise by `usernameLower`. Skips `system` users.
- `auth.ts`: `export const { auth, signIn, signOut, store, isAuthenticated } = convexAuth({ providers, callbacks })`, with:
  - **`Password({ profile(params) })`** (provider id `"password"`), used only with `flow: "signUp"`. `profile` validates `params.username` with `usernameProblem` and password length ≥ 8 (error `Passwords need at least 8 characters`). It returns `{ email: lower(email), username, usernameLower }`.
  - **`ConvexCredentials({ id: "login", authorize })`**, where `authorize({ identifier, password }, ctx)`:
    - calls `findForLogin`;
    - then `retrieveAccount(ctx, { provider: "password", account: { id: email, secret: password } })`;
    - returns `{ userId }` from the retrieved user's `_id`;
    - any miss or throw becomes `new ConvexError("Wrong username, email or password")`.

    Check the exact return shape of `retrieveAccount` in `node_modules/@convex-dev/auth/dist/server/implementation` before coding.
  - **`callbacks.createOrUpdateUser(ctx, args)`:** for a new password user, throws `That username is taken` if a user with the same `usernameLower` exists; otherwise inserts the user. Because this runs inside one mutation, the uniqueness check is atomic.
- Keys: generate `JWT_PRIVATE_KEY` and `JWKS` headlessly with `jose` exactly as `backend/.agents/skills/convex-auth/SKILL.md` step 3 says. Set them and `SITE_URL=http://127.0.0.1:8000` with `npx convex env set "NAME=VALUE"`. Delete `.auth-keys.json` afterwards.
- `auth.config.ts`: `{ providers: [{ domain: process.env.CONVEX_SITE_URL, applicationID: "convex" }] }`.

- [ ] **Step 1: Write failing tests** in `auth.test.ts`:
  - `usernameProblem("ab")`, `usernameProblem("has space")` and `usernameProblem("x".repeat(21))` all return the length/characters message; `usernameProblem("admin")` returns the reserved message; `usernameProblem("bryce_01")` returns `null`.
  - `normalizeUsername("  Bryce ")` returns `"bryce"`.
  - `findForLogin` finds a seeded user (`usernameLower: "bryce"`, email `b@x.com`) by `"bryce"` and by `"B@X.com"`; returns `null` for `"nobody"` and for the system user `animai`.
  - `createOrUpdateUser`, called twice with usernames `Bryce` and `bryce`, throws `That username is taken` the second time.
- [ ] **Step 2:** Run `npm test` and expect FAIL.
- [ ] **Step 3:** Implement the interfaces above, generate and set the keys, and add `http.ts` with `auth.addHttpRoutes(http)`.
- [ ] **Step 4:** Run `npm test` and expect PASS. Run `npx convex dev --once` and expect it ready.
- [ ] **Step 5: Round-trip check.** Using `curl` against `${CONVEX_URL}/api/action`, call `auth:signIn` with `{provider:"password", params:{flow:"signUp", email:"t1@example.com", username:"tester1", password:"password123"}}`; expect a `tokens.token`. Then call `{provider:"login", params:{identifier:"TESTER1", password:"password123"}}` and expect a token. Repeat with a wrong password and expect the exact error text. Delete `tester1` from the dashboard afterwards.
- [ ] **Step 6: Commit** `feat(convex): email+password accounts with username or email sign-in`.

### Task 3: Reading videos with access rules

**Files:**
- Create: `backend/convex/lib.ts`, `backend/convex/videos.ts`, `backend/convex/videos.test.ts`

**Interfaces:**
- `lib.ts`:
  - `requireUser(ctx): Promise<Id<"users">>` throws `ConvexError("Sign in first")` when signed out.
  - `toPublicVideo(ctx, doc, viewerId | null)` returns the shape the frontend already uses: `id`, `topic`, `title`, `status`, `stage`, `progress`, `error`, `options`, `tags`, `chapters`, `public`, `views`, `likes`, `created_at` (seconds, from `_creationTime / 1000`), `finished_at`, `video_url`, `thumbnail_url`, `captions_url`, `timings_url`, `code_url` (from `ctx.storage.getUrl`, else `null`), `author: { username }`, `ownedByMe`, `likedByMe`, `savedByMe`, `voice_name` (`options.voice` or `""`; the frontend maps it to a display name).
- `videos.ts` queries:
  - `feed({})` returns public `done` videos with a video file, newest first.
  - `get({ id })` returns the video, or `null` if it's missing or private and not owned by the viewer.
  - `myLibrary({})` returns the viewer's own videos, newest first (requires sign-in).
  - `mySaved({})` returns public saved videos by `savedAt`, newest first (requires sign-in).
  - `logs({ id })` returns up to the last 300 `jobLogs` rows (owner only, otherwise `[]`).

- [ ] **Step 1: Write failing tests** with two users A and B. A has a public done video `pub` and a private done video `priv`.
  - `feed` signed out lists `pub` only.
  - `get(priv)` returns `null` signed out and as B, and the video as A, with `ownedByMe: true`.
  - `myLibrary` as A lists both; called signed out it throws `Sign in first`.
  - `logs(pub)` as B returns `[]`.
- [ ] **Step 2:** Run `npm test` and expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `npm test` and expect PASS.
- [ ] **Step 5: Commit** `feat(convex): video queries with privacy rules`.

### Task 4: Social and owner actions

**Files:**
- Modify: `backend/convex/videos.ts`, `backend/convex/videos.test.ts`

**Interfaces:**
- Signed-in only:
  - `like({ id, liked: boolean })` returns `{ likes }`. Idempotent per user; keeps `videos.likes` in step with the `likes` rows.
  - `save({ id, saved: boolean })` returns `{ saved }`. Throws `You can't save your own video` for your own video, and `Video not found` for private or missing videos.
- Anyone:
  - `recordView({ id })` returns nothing and increments `views`, for public videos or the owner's own.
- Owner only (otherwise `Video not found`):
  - `setPublic({ id, public })`.
  - `setTags({ id, tags })`: port `clean_tags` from `backend/validate.py` exactly (lowercase, strip `#`, dedupe, ≤ 15 tags, ≤ 24 characters each) into `lib.ts` as `cleanTags`.
  - `remove({ id })`: throws `This video is still being made` while the status is active. Deletes its stored files, `jobLogs`, `likes`, `saves`, then the video.

- [ ] **Step 1: Write failing tests:**
  - `like` twice with `liked: true` leaves `likes === 1`; unlike makes it `0`; signed out it throws `Sign in first`.
  - `save` of your own video throws.
  - B saves `pub`, A deletes `pub`: B's `mySaved` returns `[]` and the `likes` and `saves` rows for `pub` are gone (Review Focus 5).
  - `setTags(["Physics", " #Waves ", "physics"])` gives `["physics", "waves"]`.
  - B calling `setPublic` on A's video throws `Video not found`.
- [ ] **Step 2:** Run `npm test` and expect FAIL. **Step 3:** Implement. **Step 4:** Run `npm test` and expect PASS.
- [ ] **Step 5: Commit** `feat(convex): likes, saves, views and owner edits`.

### Task 5: Creating videos with the daily limit

**Files:**
- Modify: `backend/convex/videos.ts`, `backend/convex/videos.test.ts`

**Interfaces:**
- `create({ topic, length, quality, narration, review, public, extra, voice })` returns `Id<"videos">`.
  - Requires sign-in.
  - Validates the topic (2–300 characters after collapsing whitespace), `length ∈ {short, medium, long}`, `quality ∈ {low, medium, high}`, and `extra` ≤ 1000 characters.
  - Inserts the video with `status: "queued"`, `stage: "Waiting in queue"`, zeros and empty arrays.
  - Throws `You've made 100 videos in the last 24 hours. Try again later.` when the owner already has 100 videos with `_creationTime` within the last 24 h. Use `by_owner` with `.order("desc")` and stop counting at 100.
- `queuePosition({ id })` returns `number`: queued videos created earlier, plus 1.

- [ ] **Step 1: Write failing tests:**
  - `create` signed out throws `Sign in first`.
  - With 100 videos seeded for A inside 24 h, `create` throws the exact limit message. With the 100 seeded 25 h ago, it succeeds.
  - A topic of `" a "` throws.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(convex): create videos with 100/day limit`.

### Task 6: Worker functions (secret-guarded)

**Files:**
- Create: `backend/convex/worker.ts`, `backend/convex/worker.test.ts`
- Modify: `backend/convex/lib.ts` (`checkSecret`)

**Interfaces** (all are public functions taking `secret: v.string()` first; `checkSecret` throws `ConvexError("Forbidden")` unless it equals `process.env.WORKER_SECRET`):
- `claimNext({ secret })` returns `{ id, topic, options, attempts } | null`. Takes the oldest `queued` video and sets `status: "writing"` and `startedAt`.
- `update({ secret, id, fields, log? })`.
  - `fields` is optional `status`, `stage`, `progress`, `attempts`, `title`, `tags`, `chapters`, `model`, `costUsd`, `error`, `finishedAt`.
  - `log` is optional `{ kind, msg, t }` and is inserted into `jobLogs`, keeping only the newest 300 per video.
- `generateUploadUrl({ secret })` returns `string`.
- `attachFiles({ secret, id, files })`: sets the given file ids and deletes any file ids they replace, so the second "polished" cut doesn't leak storage.
- `failStale({ secret })` returns `number`: every video in an active status becomes `failed` with error `The server restarted while this video was being made.`
- `importVideo({ secret, ownerUsername, video })` returns `Id<"videos">`. Used by Task 9. `ownerUsername: "animai"` creates (once) a user `{ username: "animai", usernameLower: "animai", system: true }` with no account. For other usernames, throws `No account named @<name>` if missing.

- [ ] **Step 1: Write failing tests** (set `process.env.WORKER_SECRET = "s"` in the test):
  - Any function with secret `"x"` throws `Forbidden`.
  - `claimNext` returns the oldest queued video and then `null` once nothing is queued.
  - `update` with a log keeps only the newest 300 logs after 305 inserts.
  - `failStale` turns a `rendering` video into `failed` with the exact message (Review Focus 3).
  - `importVideo` with `"animai"` twice creates one system user.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5:** Generate a 32-byte hex secret. Run `npx convex env set WORKER_SECRET=<hex>`, append `WORKER_SECRET=<hex>` to `backend/.env.local`, then run `npx convex dev --once`.
- [ ] **Step 6: Commit** `feat(convex): secret-guarded worker API`.

### Task 7: Python client for Convex

**Files:**
- Create: `backend/convex_api.py`, `backend/tests/__init__.py`, `backend/tests/test_convex_api.py`
- Modify: `backend/config.py` (load `backend/.env.local`; expose `CONVEX_URL`, `WORKER_SECRET`)

**Interfaces:**
- `class ConvexError(RuntimeError)`
- `class Convex:`
  - `__init__(url: str, secret: str)`
  - `mutation(path: str, args: dict) -> Any`: POST `{url}/api/mutation` with `{"path", "args": {"secret": ..., **args}, "format": "json"}`. Returns `value` when `status == "success"`, otherwise raises `ConvexError(errorMessage)`. Timeout 30 s, 3 retries on connection errors.
  - `query(path, args)` does the same against `/api/query`.
  - `upload(path: Path, content_type: str) -> str`: gets a URL from `worker:generateUploadUrl`, POSTs the bytes, returns `storageId`.

- [ ] **Step 1: Write failing `unittest` tests** using an `httpx.MockTransport`:
  - A success reply returns `value`.
  - An error reply raises `ConvexError` with the message.
  - `upload` POSTs the bytes to the returned URL with the given content type and returns `storageId`.
  - The secret is added to every call's `args`.
- [ ] **Step 2:** Run `.venv\Scripts\python -m unittest discover -s backend/tests` from the repo root and expect FAIL.
- [ ] **Step 3:** Implement, with `Convex` accepting an optional `transport` for tests.
- [ ] **Step 4:** Expect PASS.
- [ ] **Step 5: Commit** `feat(backend): Convex HTTP client`.

### Task 8: FastAPI as the render worker

**Files:**
- Create: `backend/worker.py`
- Modify: `backend/jobs.py`, `backend/app.py`, `backend/tests/test_worker.py` (new)

**Interfaces:**
- `jobs.py`:
  - `JobManager` keeps its pipeline methods (`_pipeline`, `_build`, `_publish`, `_review`) but now takes a `Convex` instance plus a job dict from `claimNext`.
  - `_update(**fields, log=None)` becomes `convex.mutation("worker:update", ...)`.
  - The job's working folder is `config.DATA_DIR / "work" / <id>` and is deleted after the job ends.
  - `_publish` uploads `video.mp4` (`video/mp4`), `thumbnail.jpg`, `captions.vtt` (`text/vtt`), `timings.json` and `scene.py` (`text/x-python`) with `convex.upload`, then calls `worker:attachFiles`. Tags and chapters are computed exactly as today, then sent through `update`.
  - Remove the JSON store, stats, saves, samples loading and `serialize`.
- `worker.py`: `run_forever(convex, stop: threading.Event)`.
  - Calls `failStale` once.
  - Then loops: `claimNext`; if it got a job, runs `JobManager(convex).run(job)`; otherwise waits `config.WORKER_POLL_SECONDS` (default `3`). One job at a time.
- `app.py`:
  - Keeps `GET /`, `/static`, `/api/voices`, `/api/voices/{id}/preview` and `/api/health` (drops `total_cost_usd`, adds `convex: bool`).
  - Adds `GET /api/config` returning `{"convexUrl": config.CONVEX_URL}`.
  - Removes the `/api/jobs*`, `/api/feed`, `/api/saved` routes and the `/media` and `/samples` mounts.
  - Starts `run_forever` in a daemon thread on startup when `CONVEX_URL` and `WORKER_SECRET` are set; logs a clear warning otherwise.

- [ ] **Step 1: Write failing `unittest` tests** with a fake `Convex` that records calls and patched `render_scene`, `SceneAuthor`, `make_thumbnail`, `suggest_tags` and `suggest_chapters`:
  - A successful fake run ends with an `update` call carrying `status: "done"`, and `attachFiles` receives a `video` id.
  - A `GenerationError` ends with `status: "failed"` and the error text.
  - `run_forever` calls `failStale` before the first `claimNext`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(backend): FastAPI renders jobs claimed from Convex`.

### Task 9: Import existing videos

**Files:**
- Create: `backend/import_to_convex.py`

**Interfaces:**
- CLI: `.venv\Scripts\python -m backend.import_to_convex --owner <username>`.
- For each `backend/samples/*/job.json`: upload its files and call `worker:importVideo` with `ownerUsername: "animai"`. Then for each `data/jobs/*/job.json` that is `done`, has a video and isn't a sample id: import it with `ownerUsername: <owner>`.
- Carries over `public`, `title`, `tags`, `chapters`, `options` (with `voice` defaulting to `""`), `costUsd`, `model` and views from `data/stats.json`.
- Prints one line per video. Skips a video whose `topic` and `title` already exist for that owner, so re-running is safe.

- [ ] **Step 1:** The user signs up on the new site (after Task 10) with their real username.
- [ ] **Step 2:** Run the import and expect 6 sample lines plus the user's 4 videos.
- [ ] **Step 3:** The Convex dashboard **Data → videos** shows 10 rows, and **Files** shows their media. Re-running prints only "skipped".
- [ ] **Step 4: Commit** `feat(backend): import samples and existing videos into Convex`.

### Task 10: Frontend sign-in and session

**Files:**
- Create: `frontend/convex.js`, `frontend/auth.js`
- Modify: `frontend/index.html` (load `https://unpkg.com/convex@1.48.0/dist/browser.bundle.js`, then `convex.js` and `auth.js` before `core.js`; add the sign-in panel and sidebar account markup), `frontend/styles.css`

**Interfaces:**
- `convex.js` (global functions):
  - `convexReady: Promise<void>` fetches `/api/config` and creates `new convex.ConvexClient(url)`.
  - `call(kind: "query" | "mutation" | "action", name: string, args)` resolves names with `convex.anyApi`, so `"videos:feed"` becomes `anyApi.videos.feed`.
  - `watch(name, args, onUpdate): () => void` wraps `client.onUpdate` and returns an unsubscribe function.
  - `signUp({ username, email, password })` calls `auth:signIn` with the Password `signUp` flow.
  - `signInWith({ identifier, password })` calls `auth:signIn` with provider `login`.
  - `signOutNow()`
  - `currentUser: { _id, username } | null`
  - `onAuthChange(fn)`
  - Tokens: store `token` and `refreshToken` in localStorage (try/catch). `client.setAuth(fetchToken)`, where `fetchToken({ forceRefreshToken })` calls `auth:signIn` with `{ refreshToken }` when asked to refresh.
- `auth.js`:
  - `requireSignIn(reason?: string): boolean` returns `true` if signed in; otherwise opens the panel and returns `false`.
  - The panel has "Sign in" (username or email, password) and "Create account" (username, email, password) tabs, showing the server's error text.
  - The sidebar shows `@username` and "Sign out", or a "Sign in" button.

- [ ] **Step 1:** Implement both files and the markup in the existing visual language: outlined inputs like `.search-input`, `.link-button` actions, muted caps labels.
- [ ] **Step 2: Browser check** (puppeteer script in the scratchpad, or by hand):
  - Create the account `tester2`; the sidebar shows `@tester2`.
  - Reload: still signed in.
  - Sign out, then sign in as `TESTER2`: signed in. A wrong password shows exactly `Wrong username, email or password`.
  - Creating `Tester2` again shows `That username is taken`.
- [ ] **Step 3: Commit** `feat(frontend): sign-in, sign-up and session handling`.

### Task 11: Frontend screens on Convex

**Files:**
- Modify: `frontend/core.js`, `browse.js`, `watch.js`, `library.js`, `create.js`, `app.js`

**Interfaces:**
- Replace every `api("/api/...")` call:

  | Old | New |
  |---|---|
  | `loadFeed` | `watch("videos:feed")` (keeps a live `feedPosts`) |
  | `/api/jobs/<id>` | `watch("videos:get", { id })` + `watch("videos:logs", { id })`; the create page's 1.5 s polling is removed |
  | `/api/jobs` | `videos:myLibrary` |
  | `/api/saved` | `videos:mySaved` |
  | `POST /api/jobs` | `videos:create` |
  | `/like` | `videos:like` |
  | `/save` | `videos:save` |
  | `/view` | `videos:recordView` |
  | `PATCH` | `videos:setPublic` / `videos:setTags` |
  | `DELETE` | `videos:remove` |

- Liked and saved state come from `likedByMe` and `savedByMe` (drop the localStorage liked list).
  - `author(job)` returns `@${job.author.username}`.
  - `canSave(job)` returns `!!currentUser && !job.ownedByMe`.
  - Owner controls show when `job.ownedByMe`.
- Like, Save, Generate and the Create screen call `requireSignIn()` first (Review Focus 1). Library shows a "Sign in to see your library" prompt when signed out.
- `voice_name` is the display name: look up `job.voice_name` in the `/api/voices` list, falling back to `Andrew`.

- [ ] **Step 1:** Implement screen by screen. After each one, load it in the browser and confirm no console errors.
- [ ] **Step 2: Browser checks:**
  - Signed out: the feed lists 7 public videos, the watch page plays, and Like opens the sign-in panel.
  - Two browsers signed in as different users: a like in one updates the count in the other within about 2 s.
  - A private video's link opened signed out shows "This video isn't available" (Review Focus 4).
  - Library tabs and search work.
- [ ] **Step 3: Real generation:** a short video with voice Christopher. Live progress appears without reloads, it lands in Library, and its watch page has chapters and tags.
- [ ] **Step 4: Commit** `feat(frontend): read and write through Convex with live updates`.

### Task 12: Cleanup and handoff

- [ ] **Step 1:** Delete the now-unused `backend/promote.py` and the JSON-file loops in `tagger.py` and `chapters.py`'s `__main__`. Keep `suggest_tags` and `suggest_chapters`.
- [ ] **Step 2:** Add a short "Convex" section to `backend/CLAUDE.md` covering setup for teammates: `npx convex dev --configure`, joining the `animai` project, and `WORKER_SECRET` in `.env.local`.
- [ ] **Step 3:** Run `npm test` in `backend/` and the unittest suite: both pass.
- [ ] **Step 4: Commit** `chore: remove JSON storage, document Convex setup`, then push to `main` after the user confirms.
