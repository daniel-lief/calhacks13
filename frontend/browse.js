"use strict";

// Browsing: the feed grid of public posts, and the vertical scroller that plays
// them one at a time. Each 16:9 video sits in a 9:16 frame with black above and below.

const fe = {
  grid: $("#feed-grid"), empty: $("#feed-empty"), noMatch: $("#feed-nomatch"),
  search: $("#search"), clear: $("#search-clear"), tagRow: $("#tag-row"),
  reel: $("#reel"), reelEmpty: $("#reel-empty"), hint: $("#reel-hint"),
};

let feedPosts = [];

async function loadFeed() {
  try { feedPosts = await call("query", "videos:feed"); } catch { feedPosts = []; }
  return feedPosts;
}

function statsLine(job) {
  const line = document.createElement("div");
  line.className = "stats t-16";
  line.innerHTML = `<span class="stat${job.likedByMe ? " liked" : ""}">${HEART}${compact(job.likes)}</span><span class="stat">${EYE}${compact(job.views)}</span>`;
  return line;
}

// A save toggle: a bookmark icon with a "Save" / "Saved" label
function saveToggle(job, className) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = className;
  const render = () => {
    b.classList.toggle("saved", !!job.savedByMe);
    b.setAttribute("aria-pressed", String(!!job.savedByMe));
    b.setAttribute("aria-label", job.savedByMe ? "Remove from library" : "Save to library");
    b.title = job.savedByMe ? "Saved to your library" : "Save to your library";
    b.innerHTML = `${BOOKMARK}<span>${job.savedByMe ? "Saved" : "Save"}</span>`;
  };
  render();
  b.addEventListener("click", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const pending = setSaved(job, !job.savedByMe);
    render();
    await pending;
    render();
  });
  return b;
}

// --- Search ------------------------------------------------------------------
// A filter is { q, tag }: every word of q must appear in the title, topic or tags,
// and the post must carry `tag` exactly. It lives in the address after "?", along
// with the screen's own options (`from` for the scroller, `show` for the library).

function readFilter() {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  return {
    q: params.get("q") || "", tag: params.get("tag") || "",
    from: params.get("from") || "", show: params.get("show") || "",
  };
}

function filterQuery({ q = "", tag = "", from = "", show = "" }) {
  const params = new URLSearchParams();
  if (show) params.set("show", show);
  if (from) params.set("from", from);
  if (q.trim()) params.set("q", q.trim());
  if (tag) params.set("tag", tag);
  const str = params.toString();
  return str ? `?${str}` : "";
}

function matches(job, { q, tag }) {
  const tags = job.tags || [];
  if (tag && !tags.includes(tag)) return false;
  const haystack = [job.title || "", job.topic, ...tags].join(" ").toLowerCase();
  return q.toLowerCase().split(/\s+/).filter(Boolean).every((w) => haystack.includes(w));
}

function tagChip(tag, { on = false, onClick } = {}) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = `chip${on ? " on" : ""}`;
  b.textContent = tag;
  b.setAttribute("aria-pressed", String(on));
  b.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    onClick(tag);
  });
  return b;
}

// A search bar with its tag row and no-match message, shared by the feed and the library.
// `onChange` runs after every change to the filter.
function makeSearch(els, onChange) {
  const s = {
    filter: { q: "", tag: "" },
    get filtering() { return !!(s.filter.q.trim() || s.filter.tag); },
    load(filter) { s.filter = { q: filter.q, tag: filter.tag }; els.input.value = filter.q; },
    set(filter) { s.filter = filter; onChange(); },
    toggleTag(tag) { s.set({ ...s.filter, tag: s.filter.tag === tag ? "" : tag }); },
    clear() { els.input.value = ""; s.set({ q: "", tag: "" }); els.input.focus(); },

    // Filters `posts`, refreshes the tag row and no-match message, and returns what matched
    apply(posts) {
      const shown = posts.filter((job) => matches(job, s.filter));
      els.clear.hidden = !s.filtering;

      // The most common of the tags shown on posts, plus the selected one if it's rarer.
      // A video's first tag is its broad subject, so it outranks specifics used as often.
      const counts = new Map();
      posts.forEach((job) => topTags(job).forEach((t, i) => counts.set(t, (counts.get(t) || 0) + (i === 0 ? 3 : 2))));
      const popular = [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 10).map(([t]) => t);
      if (s.filter.tag && !popular.includes(s.filter.tag)) popular.unshift(s.filter.tag);
      els.tagRow.replaceChildren(...popular.map((t) => tagChip(t, { on: t === s.filter.tag, onClick: s.toggleTag })));

      els.noMatch.hidden = !(s.filtering && shown.length === 0 && posts.length);
      if (!els.noMatch.hidden) {
        const what = [s.filter.q.trim() && `“${s.filter.q.trim()}”`, s.filter.tag && `the tag ${s.filter.tag}`]
          .filter(Boolean).join(" with ");
        els.noMatch.textContent = `Nothing matches ${what}. `;
        const clear = document.createElement("button");
        clear.type = "button";
        clear.className = "link-button";
        clear.textContent = "Clear the search";
        clear.addEventListener("click", s.clear);
        els.noMatch.appendChild(clear);
      }
      return shown;
    },
  };
  els.input.addEventListener("input", () => s.set({ ...s.filter, q: els.input.value }));
  els.input.addEventListener("keydown", (e) => { if (e.key === "Escape") s.clear(); });
  els.clear.addEventListener("click", s.clear);
  return s;
}

// --- Feed --------------------------------------------------------------------

const feedSearch = makeSearch({ input: fe.search, clear: fe.clear, tagRow: fe.tagRow, noMatch: fe.noMatch }, () => {
  history.replaceState(null, "", `#/discover${filterQuery(feedSearch.filter)}`);
  renderFeed();
});

async function showFeed() {
  feedSearch.load(readFilter());
  await loadFeed();
  renderFeed();
}

function renderFeed() {
  const shown = feedSearch.apply(feedPosts);
  fe.empty.hidden = feedPosts.length > 0;
  fe.grid.replaceChildren(...shown.map(feedTile));
}

function feedTile(job) {
  const a = document.createElement("a");
  a.className = "post";
  a.href = `#/video/${job.id}${filterQuery(feedSearch.filter)}`;

  const media = document.createElement("div");
  media.className = "post-media";
  if (job.thumbnail_url) media.style.backgroundImage = `url("${job.thumbnail_url}")`;

  // Hovering plays a silent preview, like Sora's grid
  a.addEventListener("pointerenter", () => {
    if (media.querySelector("video")) return;
    const v = document.createElement("video");
    Object.assign(v, { src: job.video_url, muted: true, loop: true, playsInline: true, autoplay: true });
    media.appendChild(v);
  });
  a.addEventListener("pointerleave", () => media.querySelector("video")?.remove());

  const caption = document.createElement("div");
  caption.className = "caption";
  const text = document.createElement("div");
  const title = document.createElement("p");
  title.className = "t-20";
  title.textContent = job.title || job.topic;
  const by = document.createElement("p");
  by.className = "t-16 muted caps";
  by.textContent = `${author(job)} - ${timeAgo(job.created_at)}`;
  text.append(title, by);
  const side = document.createElement("div");
  side.className = "caption-side";
  side.appendChild(statsLine(job));
  if (canSave(job)) side.appendChild(saveToggle(job, "save-toggle t-16"));
  caption.append(text, side);

  const tags = document.createElement("div");
  tags.className = "tag-list t-16";
  tags.append(...topTags(job).map((t) => tagChip(t, { on: t === feedSearch.filter.tag, onClick: feedSearch.toggleTag })));

  a.append(media, caption, tags);
  return a;
}

// --- Scroller ----------------------------------------------------------------

let reelItems = [];        // { job, node, video }
let reelQuery = "";        // the feed filter the scroller was opened with
let reelIndex = 0;
let reelMuted = true;
let reelObserver = null;
let wheelLock = 0;
let backdropFrame = 0;     // requestAnimationFrame id of the blurred-fill loop
let transcriptOn = readPref("animai-transcript") === "1";

function readPref(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

async function showReel(startId) {
  const filter = readFilter();
  reelQuery = filterQuery(filter);
  let source = [];
  if (filter.from === "saved") {
    try { source = currentUser ? await call("query", "videos:mySaved") : []; } catch { /* offline: empty */ }
  } else {
    source = await loadFeed();
  }
  const posts = source.filter((job) => matches(job, filter));
  fe.reelEmpty.hidden = posts.length > 0;
  fe.hint.hidden = posts.length < 2;
  reelObserver?.disconnect();
  reelItems = posts.map((job) => reelItem(job));
  fe.reel.replaceChildren(...reelItems.map((r) => r.node));

  reelObserver = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) setReelIndex(reelItems.findIndex((r) => r.node === e.target));
    }
  }, { root: fe.reel, threshold: 0.6 });
  reelItems.forEach((r) => reelObserver.observe(r.node));

  const start = Math.max(0, reelItems.findIndex((r) => r.job.id === startId));
  reelIndex = -1;
  reelItems[start]?.node.scrollIntoView({ block: "start" });
  setReelIndex(start);
  fe.reel.focus({ preventScroll: true });
}

function leaveReel() {
  reelObserver?.disconnect();
  cancelAnimationFrame(backdropFrame);
  reelItems.forEach((r) => r.video.pause());
}

function reelItem(job) {
  const node = document.createElement("article");
  node.className = "reel-item";

  const short = document.createElement("div");
  short.className = "short";

  // Blurred, enlarged copy of the video filling the space above and below it
  const backdrop = document.createElement("canvas");
  backdrop.className = "short-backdrop";
  backdrop.width = 18;
  backdrop.height = 32;
  backdrop.setAttribute("aria-hidden", "true");
  if (job.thumbnail_url) backdrop.style.backgroundImage = `url("${job.thumbnail_url}")`;

  const top = document.createElement("div");
  top.className = "short-top";
  const by = document.createElement("p");
  by.className = "t-16 muted caps";
  by.textContent = `${author(job)} - ${timeAgo(job.created_at)}`;
  const title = document.createElement("h2");
  title.className = "t-30";
  title.textContent = job.title || job.topic;
  const tags = document.createElement("div");
  tags.className = "tag-list t-16";
  for (const t of topTags(job)) {
    const link = document.createElement("a");
    link.className = "chip";
    link.href = `#/discover?tag=${encodeURIComponent(t)}`;
    link.textContent = t;
    tags.appendChild(link);
  }
  top.append(by, title, tags);

  const video = document.createElement("video");
  video.crossOrigin = "anonymous";  // media lives on Convex's domain; captions need CORS to load
  video.playsInline = true;
  video.loop = true;
  video.muted = true;
  video.preload = "none";
  video.poster = job.thumbnail_url || "";
  if (job.captions_url) video.innerHTML = `<track kind="captions" srclang="en" label="English" src="${job.captions_url}" default>`;
  video.addEventListener("click", () => (video.paused ? video.play() : video.pause()));

  const bottom = document.createElement("div");
  bottom.className = "short-bottom";
  const transcript = document.createElement("ol");
  transcript.className = "transcript t-16";
  transcript.setAttribute("aria-label", "Transcript");
  const bar = document.createElement("div");
  bar.className = "short-progress";
  const fill = document.createElement("div");
  bar.appendChild(fill);
  bottom.append(transcript);

  short.append(backdrop, top, video, bar, bottom);

  // Right-hand rail: like, views, sound
  const rail = document.createElement("div");
  rail.className = "rail t-16";
  const like = document.createElement("button");
  like.type = "button";
  like.className = "rail-button";
  const renderLike = () => {
    const on = !!job.likedByMe;
    like.classList.toggle("liked", on);
    like.setAttribute("aria-pressed", String(on));
    like.setAttribute("aria-label", on ? "Unlike" : "Like");
    like.innerHTML = `${HEART}<span>${compact(job.likes)}</span>`;
  };
  renderLike();
  like.addEventListener("click", async () => {
    const pending = setLiked(job, !job.likedByMe);
    renderLike();
    await pending;
    renderLike();
  });

  const views = document.createElement("div");
  views.className = "rail-stat";
  views.setAttribute("aria-label", `${job.views} views`);

  const sound = document.createElement("button");
  sound.type = "button";
  sound.className = "rail-button sound";
  sound.addEventListener("click", () => setMuted(!reelMuted));

  const transcriptButton = document.createElement("button");
  transcriptButton.type = "button";
  transcriptButton.className = "rail-button pill";
  transcriptButton.textContent = "Transcript";
  transcriptButton.hidden = !job.timings_url;
  transcriptButton.addEventListener("click", () => setTranscript(!transcriptOn));

  rail.append(like, ...(canSave(job) ? [saveToggle(job, "rail-button")] : []), views, transcriptButton, sound);
  node.append(short, rail);

  const r = { job, node, video, views, sound, backdrop, transcript, transcriptButton, lines: null, current: -1 };
  video.addEventListener("timeupdate", () => {
    fill.style.width = `${(video.currentTime / (video.duration || 1)) * 100}%`;
    followTranscript(r);
  });
  return r;
}

function renderRail(r) {
  r.views.innerHTML = `${EYE}<span>${compact(r.job.views)}</span>`;
  r.sound.textContent = reelMuted ? "Sound off" : "Sound on";
  r.sound.setAttribute("aria-pressed", String(!reelMuted));
  r.transcriptButton.setAttribute("aria-pressed", String(transcriptOn));
  r.transcriptButton.classList.toggle("on", transcriptOn);
  r.transcript.hidden = !transcriptOn;
  // The transcript replaces the burned-in captions while it's open
  for (const track of r.video.textTracks) track.mode = transcriptOn ? "hidden" : "showing";
}

// --- Transcript --------------------------------------------------------------

function setTranscript(on) {
  transcriptOn = on;
  try { localStorage.setItem("animai-transcript", on ? "1" : "0"); } catch { /* storage blocked */ }
  reelItems.forEach(renderRail);
  if (on && reelItems[reelIndex]) loadTranscript(reelItems[reelIndex]);
}

async function loadTranscript(r) {
  if (r.lines || !r.job.timings_url) return;
  r.lines = [];
  let segments = [];
  try { segments = (await (await fetch(r.job.timings_url)).json()).segments || []; } catch { /* leave empty */ }
  r.lines = segments.map((seg) => {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.type = "button";
    const t = document.createElement("time");
    t.textContent = formatDuration(seg.start);
    const text = document.createElement("span");
    text.textContent = seg.text;
    b.append(t, text);
    b.addEventListener("click", () => {
      r.video.currentTime = seg.start + 0.01;
      r.video.play().catch(() => {});
    });
    li.appendChild(b);
    return { start: seg.start, li };
  });
  r.transcript.replaceChildren(...r.lines.map((l) => l.li));
  r.current = -1;
  followTranscript(r);
}

// Highlight the line being spoken and keep it in the middle of the list
function followTranscript(r) {
  if (!(transcriptOn || r.alwaysOn) || !r.lines?.length) return;
  const t = r.video.currentTime;
  let i = r.lines.findIndex((l, j) => t >= l.start && (j === r.lines.length - 1 || t < r.lines[j + 1].start));
  if (i === r.current) return;
  r.lines[r.current]?.li.classList.remove("current");
  r.current = i;
  const line = r.lines[i]?.li;
  if (!line) return;
  line.classList.add("current");
  r.transcript.scrollTo({ top: line.offsetTop - r.transcript.clientHeight / 2 + line.offsetHeight / 2, behavior: "smooth" });
}

// --- Blurred fill --------------------------------------------------------------

// Paints the active video, cropped to 9:16, onto its tiny backdrop canvas; CSS blurs it up
function runBackdrop(r) {
  cancelAnimationFrame(backdropFrame);
  const ctx = r.backdrop.getContext("2d");
  const paint = () => {
    const v = r.video;
    if (v.readyState >= 2 && v.videoWidth && (!v.paused || !r.backdrop.classList.contains("live"))) {
      const sw = Math.min(v.videoWidth, (v.videoHeight * 9) / 16);
      ctx.drawImage(v, (v.videoWidth - sw) / 2, 0, sw, v.videoHeight, 0, 0, r.backdrop.width, r.backdrop.height);
      r.backdrop.classList.add("live");
    }
    backdropFrame = requestAnimationFrame(paint);
  };
  paint();
}

function setReelIndex(i) {
  if (i < 0 || i === reelIndex) return;
  reelIndex = i;
  reelItems.forEach((r, j) => {
    // Load the visible video and its neighbours; pause everything else
    if (Math.abs(j - i) <= 1 && !r.video.src) r.video.src = r.job.video_url;
    if (j === i) {
      r.video.muted = reelMuted;
      r.video.currentTime = 0;
      r.video.play().catch(() => {});
      countView(r.job);
      runBackdrop(r);
      if (transcriptOn) loadTranscript(r);
    } else {
      r.video.pause();
    }
    renderRail(r);
  });
  history.replaceState(null, "", `#/watch/${reelItems[i].job.id}${reelQuery}`);
  if (i > 0) fe.hint.hidden = true;
}

function setMuted(muted) {
  reelMuted = muted;
  reelItems.forEach((r, j) => {
    if (j === reelIndex) r.video.muted = muted;
    renderRail(r);
  });
}

function reelGo(step) {
  const next = Math.max(0, Math.min(reelItems.length - 1, reelIndex + step));
  reelItems[next]?.node.scrollIntoView({ behavior: "smooth", block: "start" });
}

// One video per wheel gesture, however many wheel events a trackpad sends
fe.reel.addEventListener("wheel", (e) => {
  if (e.target.closest(".transcript")) return;   // let the transcript scroll itself
  e.preventDefault();
  if (Math.abs(e.deltaY) < 4 || performance.now() < wheelLock) return;
  wheelLock = performance.now() + 700;
  reelGo(e.deltaY > 0 ? 1 : -1);
}, { passive: false });

document.addEventListener("keydown", (e) => {
  if ($("#screen-watch").hidden || e.target.closest("input, textarea")) return;
  const r = reelItems[reelIndex];
  if (["ArrowDown", "PageDown", "j"].includes(e.key)) reelGo(1);
  else if (["ArrowUp", "PageUp", "k"].includes(e.key)) reelGo(-1);
  else if (e.key === " " && r) r.video.paused ? r.video.play() : r.video.pause();
  else if (e.key === "m") setMuted(!reelMuted);
  else return;
  e.preventDefault();
});
