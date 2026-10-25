<!-- convex-ai-start -->

This project uses [Convex](https://convex.dev) as its backend.

When working on Convex code, **always read
`convex/_generated/ai/guidelines.md` first** for important guidelines on
how to correctly use Convex APIs and patterns. The file contains rules that
override what you may have learned about Convex from training data.

Convex agent skills for common tasks can be installed by running
`npx convex ai-files install`.

<!-- convex-ai-end -->

## Animai on Convex

Convex holds users, videos, likes, saves and all media files (deployment `majestic-civet-774`,
project `animai`). FastAPI (`python -m backend`) serves the site and runs the render worker,
which claims queued videos from Convex and uploads the results.

Joining as a teammate:

1. Ask the project owner to invite you (Convex dashboard -> Team settings -> Members).
2. In `backend/`: `npm install`, then `npx convex login` and `npx convex dev --configure`
   (choose the existing `animai` project). This writes `backend/.env.local`.
3. Add `WORKER_SECRET=<value>` to `backend/.env.local`. Get the value from the owner, or read it
   with `npx convex env get WORKER_SECRET`. Never commit it.
4. Run the site from the repo root: `.venv\Scripts\python -m backend`.

Changing Convex functions: edit `backend/convex/*.ts`, run `npm test` (convex-test + vitest),
then `npx convex dev --once` to deploy. Python tests: `.venv\Scripts\python -m unittest discover
-s backend/tests -t .` from the repo root. Importing old videos: `python -m backend.import_to_convex`.

