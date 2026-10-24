"use strict";

// Watch page: one video in 16:9, laid out like YouTube. The player and details on
// the left; the transcript and "Up next" on the right. Opened from the feed and the
// library (the Scroll screen stays vertical).
//
// The address says where it was opened from, which decides what's up next:
//   #/video/<id>                 the feed (with its search, if any)
//   #/video/<id>?from=saved      your saved videos
//   #/video/<id>?from=library    your library (finished videos you made, plus saved)

const wv = {
  video: $("#watch-video"), title: $("#watch-title"), meta: $("#watch-meta"), actions: $("#watch-actions"),
  tags: $("#watch-tags"), prompt: $("#watch-prompt"), owner: $("#watch-owner"), chapters: $("#watch-chapters"),
  publicToggle: $("#watch-public"), editTags: $("#watch-edit-tags"), toggleCode: $("#watch-toggle-code"),
  download: $("#watch-download"), remove: $("#watch-delete"),
  tagForm: $("#watch-tag-form"), tagInput: $("#watch-tag-input"), tagCancel: $("#watch-tag-cancel"),
  code: $("#watch-code"), codeText: $("#watch-code-text"), copyCode: $("#watch-copy-code"),
  transcriptWrap: $("#watch-transcript-wrap"), transcript: $("#watch-transcript"),
  upNext: $("#up-next"), missing: $("#watch-missing"), layout: $("#screen-video .watch"),
};

const watchPlayer = enhancePlayer(wv.video);

let watching = null;      // { job, video, transcript, lines, current, alwaysOn } — shaped for the transcript helpers
let watchQuery = "";

async function showVideo(id) {
  const filter = readFilter();
  watchQuery = filterQuery(filter);
  wv.video.pause();
  wv.code.hidden = true;
  wv.tagForm.hidden = true;

  let job;
  try { job = await api(`/api/jobs/${id}`); } catch { job = null; }
  if ($("#screen-video").hidden) return;
  wv.layout.hidden = !job;
  wv.missing.hidden = !!job;
  if (!job) return;

  watching = { job, video: wv.video, transcript: wv.transcript, lines: null, current: -1, alwaysOn: true };
  renderWatch(job);
  renderChapterList(job);

  wv.video.innerHTML = job.captions_url
    ? `<track kind="captions" srclang="en" label="English" src="${job.captions_url}">`
    : "";
  wv.video.poster = job.thumbnail_url || "";
  wv.video.src = job.video_url;
  wv.video.muted = false;
  watchPlayer.setTitle(job.title || job.topic);
  watchPlayer.setChapters(job.chapters);
  // Arriving here was a click, so sound is usually allowed; if not, start muted
  wv.video.play().catch(() => { wv.video.muted = true; wv.video.play().catch(() => {}); });
  countView(job);

  wv.transcriptWrap.hidden = !job.timings_url;
  wv.transcript.replaceChildren();
  loadTranscript(watching);
  renderUpNext(job, filter);
}

function leaveVideo() {
  wv.video.pause();
  watching = null;
}

wv.video.addEventListener("timeupdate", () => {
  if (!watching) return;
  followTranscript(watching);
  // Highlight the chapter being played in the details box
  const t = wv.video.currentTime;
  const items = [...wv.chapters.children];
  const at = items.findLastIndex((li) => t >= Number(li.dataset.start));
  items.forEach((li, i) => li.classList.toggle("current", i === at));
});

function renderChapterList(job) {
  const chapters = job.chapters || [];
  wv.chapters.hidden = chapters.length < 2;
  wv.chapters.replaceChildren(...chapters.map((c) => {
    const li = document.createElement("li");
    li.dataset.start = c.start;
    const b = document.createElement("button");
    b.type = "button";
    b.innerHTML = `<time>${formatDuration(c.start)}</time><span></span>`;
    b.lastChild.textContent = c.title;
    b.addEventListener("click", () => {
      wv.video.currentTime = c.start + 0.01;
      wv.video.play().catch(() => {});
    });
    li.appendChild(b);
    return li;
  }));
}

function renderWatch(job) {
  wv.title.textContent = job.title || job.topic;
  wv.meta.textContent = `${author(job)} - ${timeAgo(job.created_at)} - ${plural(job.views || 0, "view")}`;
  wv.prompt.textContent = `Prompt: ${job.topic}`;
  wv.tags.replaceChildren(...topTags(job).map((t) => {
    const link = document.createElement("a");
    link.className = "chip";
    link.href = `#/feed?tag=${encodeURIComponent(t)}`;
    link.textContent = t;
    return link;
  }));

  // Like, save, and a way over to the vertical view
  const like = document.createElement("button");
  like.type = "button";
  like.className = "watch-action";
  const renderLike = () => {
    const on = likedIds.has(job.id);
    like.classList.toggle("liked", on);
    like.setAttribute("aria-pressed", String(on));
    like.setAttribute("aria-label", on ? "Unlike" : "Like");
    like.innerHTML = `${HEART}<span>${compact(job.likes)}</span>`;
  };
  renderLike();
  like.addEventListener("click", async () => {
    const on = !likedIds.has(job.id);
    job.likes = Math.max(0, (job.likes || 0) + (on ? 1 : -1));
    const pending = setLiked(job, on);
    renderLike();
    await pending;
    renderLike();
  });
  const actions = [like];
  if (canSave(job)) actions.push(saveToggle(job, "watch-action"));
  if (job.public) {
    const vertical = document.createElement("a");
    vertical.className = "watch-action";
    vertical.href = `#/watch/${job.id}`;
    vertical.textContent = "Watch in Scroll";
    actions.push(vertical);
  }
  wv.actions.replaceChildren(...actions);

  // Controls for your own videos
  wv.owner.hidden = job.sample;
  if (!job.sample) {
    wv.publicToggle.textContent = job.public ? "Public" : "Private";
    wv.publicToggle.title = job.public ? "Shown in the feed. Click to make private." : "Only in your library. Click to post to the feed.";
    wv.toggleCode.hidden = !job.code_url;
    wv.toggleCode.textContent = wv.code.hidden ? "View code" : "Hide code";
    wv.download.href = job.video_url;
    wv.download.download = `${slug(job.title || job.topic)}.mp4`;
  }
}

// --- Up next -------------------------------------------------------------------

async function renderUpNext(job, filter) {
  let list = [];
  if (filter.from === "saved") {
    list = await api("/api/saved").catch(() => []);
  } else if (filter.from === "library") {
    const [created, saved] = await Promise.all([api("/api/jobs").catch(() => []), api("/api/saved").catch(() => [])]);
    list = [...created.filter((j) => j.status === "done" && j.has_video), ...saved].sort((a, b) => b.created_at - a.created_at);
  } else {
    list = (await loadFeed()).filter((j) => matches(j, filter));
  }
  if (watching?.job.id !== job.id) return;

  // What comes after this video in the list, then wrap around to the start
  const at = list.findIndex((j) => j.id === job.id);
  const next = at >= 0 ? [...list.slice(at + 1), ...list.slice(0, at)] : list.filter((j) => j.id !== job.id);
  wv.upNext.replaceChildren(...next.map(upNextItem));
  if (!next.length) wv.upNext.innerHTML = `<p class="t-16 muted">Nothing else here yet.</p>`;
}

function upNextItem(job) {
  const a = document.createElement("a");
  a.className = "up-next-item";
  a.href = `#/video/${job.id}${watchQuery}`;
  const thumb = document.createElement("div");
  thumb.className = "up-next-thumb";
  if (job.thumbnail_url) thumb.style.backgroundImage = `url("${job.thumbnail_url}")`;
  const text = document.createElement("div");
  const title = document.createElement("p");
  title.className = "t-16";
  title.textContent = job.title || job.topic;
  const meta = document.createElement("p");
  meta.className = "t-16 muted caps";
  meta.textContent = `${author(job)} - ${plural(job.views || 0, "view")}`;
  text.append(title, meta);
  a.append(thumb, text);
  return a;
}

// --- Owner controls ------------------------------------------------------------

wv.publicToggle.addEventListener("click", async () => {
  const job = watching?.job;
  if (!job) return;
  try {
    const updated = await api(`/api/jobs/${job.id}`, { method: "PATCH", body: JSON.stringify({ public: !job.public }) });
    job.public = updated.public;
    renderWatch(job);
  } catch (err) { alert(err.message); }
});

wv.editTags.addEventListener("click", () => {
  wv.tagInput.value = (watching?.job.tags || []).join(", ");
  wv.tagForm.hidden = false;
  wv.tagInput.focus();
});
wv.tagCancel.addEventListener("click", () => { wv.tagForm.hidden = true; });
wv.tagInput.addEventListener("keydown", (e) => { if (e.key === "Escape") wv.tagForm.hidden = true; });
wv.tagForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const job = watching?.job;
  if (!job) return;
  const tags = wv.tagInput.value.split(",").map((t) => t.trim()).filter(Boolean);
  try {
    const updated = await api(`/api/jobs/${job.id}`, { method: "PATCH", body: JSON.stringify({ tags }) });
    job.tags = updated.tags;
    wv.tagForm.hidden = true;
    renderWatch(job);
  } catch (err) { alert(`Couldn't save tags: ${err.message}`); }
});

wv.toggleCode.addEventListener("click", async () => {
  const job = watching?.job;
  if (!job?.code_url) return;
  wv.code.hidden = !wv.code.hidden;
  wv.toggleCode.textContent = wv.code.hidden ? "View code" : "Hide code";
  if (wv.code.hidden || wv.codeText.dataset.for === job.id) return;
  try {
    const text = await (await fetch(`${job.code_url}?v=${Date.now()}`)).text();
    wv.codeText.innerHTML = highlightPython(text);
    wv.codeText.dataset.raw = text;
    wv.codeText.dataset.for = job.id;
  } catch {
    wv.codeText.textContent = "Couldn't load the code.";
  }
});

wv.copyCode.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(wv.codeText.dataset.raw || "");
    wv.copyCode.textContent = "Copied";
    setTimeout(() => (wv.copyCode.textContent = "Copy"), 1500);
  } catch { /* clipboard unavailable */ }
});

wv.remove.addEventListener("click", async () => {
  const job = watching?.job;
  if (!job || !confirm(`Delete “${job.title || job.topic}”?`)) return;
  try {
    await api(`/api/jobs/${job.id}`, { method: "DELETE" });
    location.hash = "#/library";
  } catch (err) { alert(err.message); }
});
