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

const SIGNED_OUT_LIBRARY = "<button type=\"button\" class=\"link-button\" data-sign-in>Sign in</button> to see the videos you've made and saved.";

let libraryUnsubs = [];      // live Convex queries while the library is open
let libraryShow = "";        // "" (all) | "created" | "saved"
let createdJobs = [];
let savedJobs = [];

const librarySearch = makeSearch(
  { input: lib.search, clear: lib.clear, tagRow: lib.tagRow, noMatch: lib.noMatch },
  () => renderLibrary(),
);

function showLibrary() {
  leaveLibrary();
  const filter = readFilter();
  libraryShow = ["created", "saved"].includes(filter.show) ? filter.show : "";
  librarySearch.load(filter);
  createdJobs = [];
  savedJobs = [];
  if (!currentUser) {
    renderLibrary();
    return;
  }
  // Live: progress of videos being made, new saves and deletions show up by themselves
  libraryUnsubs = [
    watch("videos:myLibrary", {}, (rows) => { createdJobs = rows; renderLibrary(); }),
    watch("videos:mySaved", {}, (rows) => { savedJobs = rows; renderLibrary(); }),
  ];
}

function leaveLibrary() {
  libraryUnsubs.forEach((stop) => stop());
  libraryUnsubs = [];
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
  lib.empty.innerHTML = currentUser ? EMPTY_LIBRARY[libraryShow] : SIGNED_OUT_LIBRARY;
  lib.empty.querySelector("[data-sign-in]")?.addEventListener("click", () => openAuth());
  lib.grid.replaceChildren(...shown.map((job) => (job.ownedByMe ? libraryTile(job) : savedTile(job))));
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
        await call("mutation", "videos:setPublic", { id: job.id, public: !job.public });  // live query re-renders
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
        await call("mutation", "videos:remove", { id: job.id });
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
    await setSaved(job, false);   // the live query drops it from the list
  });
  actions.appendChild(unsave);

  caption.append(text, actions);
  a.append(media, caption, tileTags(job));
  return a;
}
