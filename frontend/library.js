"use strict";

// Library: the videos you've made (including ones in progress, failed or private)
// and the ones you've saved from the feed, with the same search as the feed.

const lib = {
  grid: $("#library-grid"), empty: $("#library-empty"), noMatch: $("#library-nomatch"),
  tabs: $("#library-tabs"), search: $("#library-search"), clear: $("#library-search-clear"), tagRow: $("#library-tag-row"),
};

const EMPTY_LIBRARY = {
  "": "Nothing here yet. <a class=\"inline-link\" href=\"#/create\">Make a video</a> or save one from <a class=\"inline-link\" href=\"#/discover\">Discover</a>.",
  created: "You haven't made a video yet. <a class=\"inline-link\" href=\"#/create\">Make your first one</a>.",
  saved: "Nothing saved yet. Press Save on a video in <a class=\"inline-link\" href=\"#/discover\">Discover</a> to keep it here.",
};

let libraryTimer = null;
let libraryShow = "";        // "" (all) | "created" | "saved"
let createdJobs = [];
let savedJobs = [];

const librarySearch = makeSearch(
  { input: lib.search, clear: lib.clear, tagRow: lib.tagRow, noMatch: lib.noMatch },
  () => renderLibrary(),
);

async function showLibrary() {
  clearTimeout(libraryTimer);
  const filter = readFilter();
  libraryShow = ["created", "saved"].includes(filter.show) ? filter.show : "";
  librarySearch.load(filter);
  const [created, saved] = await Promise.all([
    api("/api/jobs").catch(() => []),
    api("/api/saved").catch(() => []),
  ]);
  if ($("#screen-library").hidden) return;
  createdJobs = created;
  savedJobs = saved;
  renderLibrary();
  if (createdJobs.some((j) => ACTIVE.has(j.status))) libraryTimer = setTimeout(showLibrary, 5000);
}

function leaveLibrary() {
  clearTimeout(libraryTimer);
}

function renderLibrary() {
  history.replaceState(null, "", `#/library${filterQuery({ ...librarySearch.filter, show: libraryShow })}`);

  const counts = { "": createdJobs.length + savedJobs.length, created: createdJobs.length, saved: savedJobs.length };
  lib.tabs.querySelectorAll("button").forEach((b) => {
    const on = b.dataset.show === libraryShow;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", String(on));
    b.dataset.count = counts[b.dataset.show];
  });

  const list = libraryShow === "created" ? createdJobs
    : libraryShow === "saved" ? savedJobs
    : [...createdJobs, ...savedJobs].sort((a, b) => b.created_at - a.created_at);
  const shown = librarySearch.apply(list);

  lib.empty.hidden = list.length > 0;
  lib.empty.innerHTML = EMPTY_LIBRARY[libraryShow];
  lib.grid.replaceChildren(...shown.map((job) => (job.sample ? savedTile(job) : libraryTile(job))));
}

lib.tabs.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-show]");
  if (!b) return;
  libraryShow = b.dataset.show;
  renderLibrary();
});

function tileTags(job) {
  const tags = document.createElement("div");
  tags.className = "tag-list t-16";
  tags.append(...topTags(job).map((t) => tagChip(t, { on: t === librarySearch.filter.tag, onClick: librarySearch.toggleTag })));
  return tags;
}

// A video you made: finished ones open the watch page; ones in progress (or failed)
// open the page that shows how making it is going
function libraryTile(job) {
  const a = document.createElement("a");
  a.className = "post";
  a.href = job.status === "done" && job.has_video ? `#/video/${job.id}?from=library` : `#/v/${job.id}`;

  const media = document.createElement("div");
  media.className = "post-media";
  if (job.thumbnail_url) media.style.backgroundImage = `url("${job.thumbnail_url}")`;
  if (job.status !== "done") {
    const note = document.createElement("span");
    note.className = "post-note t-16 caps";
    note.textContent = ACTIVE.has(job.status) ? `${STATUS_LABEL[job.status]} - ${Math.round(job.progress * 100)}%` : "Failed";
    media.appendChild(note);
  }

  const caption = document.createElement("div");
  caption.className = "caption";
  const text = document.createElement("div");
  const title = document.createElement("p");
  title.className = "t-20";
  title.textContent = job.title || job.topic;
  const meta = document.createElement("p");
  meta.className = "t-16 muted caps";
  meta.textContent = `Created - ${timeAgo(job.created_at)}`;
  text.append(title, meta);

  const actions = document.createElement("div");
  actions.className = "caption-meta t-16";
  if (job.status === "done") {
    const vis = document.createElement("button");
    vis.type = "button";
    const render = () => {
      vis.textContent = job.public ? "Public" : "Private";
      vis.title = job.public ? "Visible on Discover. Click to make private." : "Only in your library. Click to make public.";
      vis.classList.toggle("on", job.public);
    };
    render();
    vis.addEventListener("click", async (e) => {
      e.preventDefault();
      try {
        const updated = await api(`/api/jobs/${job.id}`, { method: "PATCH", body: JSON.stringify({ public: !job.public }) });
        job.public = updated.public;
        render();
      } catch (err) { alert(err.message); }
    });
    actions.appendChild(vis);
  }
  if (!ACTIVE.has(job.status)) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.innerHTML = TRASH;
    remove.className = "icon-button";
    remove.title = "Delete video";
    remove.setAttribute("aria-label", `Delete “${job.title || job.topic}”`);
    remove.addEventListener("click", async (e) => {
      e.preventDefault();
      if (!confirm(`Delete “${job.title || job.topic}”?`)) return;
      try {
        await api(`/api/jobs/${job.id}`, { method: "DELETE" });
        showLibrary();
      } catch (err) { alert(err.message); }
    });
    actions.appendChild(remove);
  }
  caption.append(text, actions);
  a.append(media, caption, tileTags(job));
  return a;
}

// A video saved from the feed: opens the watch page, with your other saves up next
function savedTile(job) {
  const a = document.createElement("a");
  a.className = "post";
  a.href = `#/video/${job.id}?from=saved`;

  const media = document.createElement("div");
  media.className = "post-media";
  if (job.thumbnail_url) media.style.backgroundImage = `url("${job.thumbnail_url}")`;

  const caption = document.createElement("div");
  caption.className = "caption";
  const text = document.createElement("div");
  const title = document.createElement("p");
  title.className = "t-20";
  title.textContent = job.title || job.topic;
  const meta = document.createElement("p");
  meta.className = "t-16 muted caps";
  meta.textContent = `Saved - ${author(job)}`;
  text.append(title, meta);

  const actions = document.createElement("div");
  actions.className = "caption-meta t-16";
  const unsave = document.createElement("button");
  unsave.type = "button";
  unsave.innerHTML = REMOVE;
  unsave.className = "icon-button";
  unsave.setAttribute("aria-label", `Remove “${job.title || job.topic}” from library`);
  unsave.title = "Remove from your library";
  unsave.addEventListener("click", async (e) => {
    e.preventDefault();
    if (await setSaved(job, false)) return;   // still saved: the request failed
    savedJobs = savedJobs.filter((j) => j.id !== job.id);
    renderLibrary();
  });
  actions.appendChild(unsave);

  caption.append(text, actions);
  a.append(media, caption, tileTags(job));
  return a;
}
