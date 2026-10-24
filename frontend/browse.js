"use strict";

// Browsing: the feed grid of public posts, and the vertical scroller that plays
// them one at a time. Each 16:9 video sits in a 9:16 frame with black above and below.

const fe = {
  grid: $("#feed-grid"), count: $("#feed-count"), empty: $("#feed-empty"),
  reel: $("#reel"), reelEmpty: $("#reel-empty"), hint: $("#reel-hint"),
};

let feedPosts = [];

async function loadFeed() {
  try { feedPosts = await api("/api/feed"); } catch { feedPosts = []; }
  return feedPosts;
}

function statsLine(job) {
  const line = document.createElement("div");
  line.className = "stats t-16";
  line.innerHTML = `<span class="stat${likedIds.has(job.id) ? " liked" : ""}">${HEART}${compact(job.likes)}</span><span class="stat">${EYE}${compact(job.views)}</span>`;
  return line;
}

// --- Feed --------------------------------------------------------------------

async function showFeed() {
  const posts = await loadFeed();
  fe.count.textContent = plural(posts.length, "video");
  fe.empty.hidden = posts.length > 0;
  fe.grid.replaceChildren(...posts.map(feedTile));
}

function feedTile(job) {
  const a = document.createElement("a");
  a.className = "post";
  a.href = `#/watch/${job.id}`;

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
  caption.append(text, statsLine(job));

  a.append(media, caption);
  return a;
}

// --- Scroller ----------------------------------------------------------------

let reelItems = [];        // { job, node, video }
let reelIndex = 0;
let reelMuted = true;
let reelObserver = null;
let wheelLock = 0;

async function showReel(startId) {
  const posts = await loadFeed();
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
  reelItems.forEach((r) => r.video.pause());
}

function reelItem(job) {
  const node = document.createElement("article");
  node.className = "reel-item";

  const short = document.createElement("div");
  short.className = "short";

  const top = document.createElement("div");
  top.className = "short-top";
  const by = document.createElement("p");
  by.className = "t-16 muted caps";
  by.textContent = `${author(job)} - ${timeAgo(job.created_at)}`;
  const title = document.createElement("h2");
  title.className = "t-30";
  title.textContent = job.title || job.topic;
  top.append(by, title);

  const video = document.createElement("video");
  video.playsInline = true;
  video.loop = true;
  video.muted = true;
  video.preload = "none";
  video.poster = job.thumbnail_url || "";
  if (job.captions_url) video.innerHTML = `<track kind="captions" srclang="en" label="English" src="${job.captions_url}" default>`;
  video.addEventListener("click", () => (video.paused ? video.play() : video.pause()));

  const bottom = document.createElement("div");
  bottom.className = "short-bottom";
  const prompt = document.createElement("p");
  prompt.className = "t-16 muted";
  prompt.textContent = `Prompt: ${job.topic}`;
  const bar = document.createElement("div");
  bar.className = "short-progress";
  const fill = document.createElement("div");
  bar.appendChild(fill);
  bottom.append(prompt);
  video.addEventListener("timeupdate", () => {
    fill.style.width = `${(video.currentTime / (video.duration || 1)) * 100}%`;
  });

  short.append(top, video, bar, bottom);

  // Right-hand rail: like, views, sound
  const rail = document.createElement("div");
  rail.className = "rail t-16";
  const like = document.createElement("button");
  like.type = "button";
  like.className = "rail-button";
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

  const views = document.createElement("div");
  views.className = "rail-stat";
  views.setAttribute("aria-label", `${job.views} views`);

  const sound = document.createElement("button");
  sound.type = "button";
  sound.className = "rail-button sound";
  sound.addEventListener("click", () => setMuted(!reelMuted));

  rail.append(like, views, sound);
  node.append(short, rail);
  return { job, node, video, views, sound };
}

function renderRail(r) {
  r.views.innerHTML = `${EYE}<span>${compact(r.job.views)}</span>`;
  r.sound.textContent = reelMuted ? "Sound off" : "Sound on";
  r.sound.setAttribute("aria-pressed", String(!reelMuted));
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
    } else {
      r.video.pause();
    }
    renderRail(r);
  });
  history.replaceState(null, "", `#/watch/${reelItems[i].job.id}`);
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
