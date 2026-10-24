"use strict";

// Library: every video you've made, including ones in progress, failed or private.

const lib = { grid: $("#library-grid"), count: $("#library-count"), empty: $("#library-empty") };

let libraryTimer = null;

async function showLibrary() {
  clearTimeout(libraryTimer);
  let jobs = [];
  try { jobs = await api("/api/jobs"); } catch { /* offline: show empty */ }
  if ($("#screen-library").hidden) return;
  lib.count.textContent = plural(jobs.length, "video");
  lib.empty.hidden = jobs.length > 0;
  lib.grid.replaceChildren(...jobs.map(libraryTile));
  if (jobs.some((j) => ACTIVE.has(j.status))) libraryTimer = setTimeout(showLibrary, 5000);
}

function leaveLibrary() {
  clearTimeout(libraryTimer);
}

function libraryTile(job) {
  const a = document.createElement("a");
  a.className = "post";
  a.href = `#/v/${job.id}`;

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
  meta.textContent = timeAgo(job.created_at);
  text.append(title, meta);

  const actions = document.createElement("div");
  actions.className = "caption-meta t-16";
  if (job.status === "done") {
    const vis = document.createElement("button");
    vis.type = "button";
    const render = () => {
      vis.textContent = job.public ? "Public" : "Private";
      vis.title = job.public ? "Shown in the feed. Click to make private." : "Only in your library. Click to post to the feed.";
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
    remove.textContent = "Delete";
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
  a.append(media, caption);
  return a;
}
