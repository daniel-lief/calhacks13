"use strict";

// Themed controls for a <video>, replacing the browser's default ones: a big play
// button, a scrub bar split into chapters, time, volume,
// captions, speed and fullscreen. Controls fade out while the video plays and the
// pointer is still, leaving a thin progress line.
//
//   const player = enhancePlayer(videoElement);   once per element; changing src later is fine
//   player.setChapters([{ start, title }])         split the scrub bar into titled chapters
//   player.setTitle(text)                          shown at the top in fullscreen
//
// Keys (anywhere on the page while the player is on screen, except when typing):
// space or K play/pause, ← → seek 5 s, J L seek 10 s, M mute, C captions, F fullscreen.

const PLAYER_ICONS = {
  play: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5v15l12.5-7.5z"/></svg>`,
  pause: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5h3.5v15H7zM13.5 4.5H17v15h-3.5z"/></svg>`,
  volume: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path class="line" d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>`,
  muted: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path class="line" d="M16 9.5l5 5M21 9.5l-5 5"/></svg>`,
  enter: `<svg viewBox="0 0 24 24" aria-hidden="true"><path class="line" d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/></svg>`,
  exit: `<svg viewBox="0 0 24 24" aria-hidden="true"><path class="line" d="M9 4v5H4M20 9h-5V4M15 20v-5h5M4 15h5v5"/></svg>`,
  back: `<svg viewBox="0 0 24 24" aria-hidden="true"><path class="line" d="M11 7l-5 5 5 5M18 7l-5 5 5 5"/></svg>`,
  forward: `<svg viewBox="0 0 24 24" aria-hidden="true"><path class="line" d="M6 7l5 5-5 5M13 7l5 5-5 5"/></svg>`,
};
const SPEEDS = [1, 1.25, 1.5, 2, 0.75];
const players = new Set();   // shells, for the page-wide keyboard shortcuts

function enhancePlayer(video) {
  video.removeAttribute("controls");
  video.crossOrigin = "anonymous";  // media lives on Convex's domain; captions need CORS to load
  const shell = document.createElement("div");
  shell.className = "player-shell paused";
  shell.tabIndex = 0;
  shell.setAttribute("role", "region");
  shell.setAttribute("aria-label", "Video player");
  video.replaceWith(shell);

  shell.innerHTML = `
    <div class="pl-top"><p class="pl-title"></p></div>
    <div class="pl-spinner" aria-hidden="true"></div>
    <div class="pl-flash" aria-hidden="true"></div>
    <div class="pl-seek pl-seek-back" aria-hidden="true">${PLAYER_ICONS.back}<span></span></div>
    <div class="pl-seek pl-seek-forward" aria-hidden="true">${PLAYER_ICONS.forward}<span></span></div>
    <button class="pl-big" type="button" aria-label="Play">${PLAYER_ICONS.play}</button>
    <div class="pl-mini" aria-hidden="true"><div></div></div>
    <div class="pl-bar">
      <div class="pl-scrub" role="slider" tabindex="-1" aria-label="Seek" aria-valuemin="0">
        <div class="pl-chapters"></div>
        <div class="pl-thumb"></div>
        <div class="pl-tip"><span class="pl-tip-time"></span><span class="pl-tip-text"></span></div>
      </div>
      <div class="pl-row">
        <button class="pl-btn pl-play" type="button" aria-label="Play">${PLAYER_ICONS.play}</button>
        <div class="pl-volume">
          <button class="pl-btn pl-mute" type="button" aria-label="Mute">${PLAYER_ICONS.volume}</button>
          <input class="pl-vol" type="range" min="0" max="1" step="0.05" value="1" aria-label="Volume">
        </div>
        <span class="pl-time"><span class="pl-now">0:00</span><span class="pl-sep">/</span><span class="pl-total">0:00</span></span>
        <span class="pl-chapter"></span>
        <span class="pl-spacer"></span>
        <button class="pl-btn pl-text pl-cc" type="button" aria-label="Captions" aria-pressed="false">CC</button>
        <button class="pl-btn pl-text pl-speed" type="button" aria-label="Playback speed">1x</button>
        <button class="pl-btn pl-full" type="button" aria-label="Full screen">${PLAYER_ICONS.enter}</button>
      </div>
    </div>`;
  shell.prepend(video);
  players.add(shell);

  const q = (sel) => shell.querySelector(sel);
  const big = q(".pl-big"), play = q(".pl-play"), scrub = q(".pl-scrub"), chaptersEl = q(".pl-chapters");
  const thumb = q(".pl-thumb"), tip = q(".pl-tip"), tipTime = q(".pl-tip-time"), tipText = q(".pl-tip-text");
  const now = q(".pl-now"), total = q(".pl-total"), chapterLabel = q(".pl-chapter"), mini = q(".pl-mini div");
  const mute = q(".pl-mute"), vol = q(".pl-vol"), cc = q(".pl-cc"), speed = q(".pl-speed"), full = q(".pl-full");
  const flash = q(".pl-flash"), title = q(".pl-title");

  // Chapters: [{ start, end, title, el, fill, buffer }]. Without any, one spans the video.
  let chapters = [];

  const toggle = () => (video.paused || video.ended ? video.play().catch(() => {}) : video.pause());
  const duration = () => video.duration || 0;

  function buildChapters(given) {
    const d = duration();
    const list = given.length && d ? given : [{ start: 0, title: "" }];
    chapters = list.map((seg, i) => {
      const el = document.createElement("div");
      el.className = "pl-chapter-seg";
      const end = i + 1 < list.length ? list[i + 1].start : d;
      el.style.flexGrow = String(Math.max(0.001, d ? end - seg.start : 1));
      el.innerHTML = `<div class="pl-buffer"></div><div class="pl-fill"></div>`;
      return { start: seg.start, end, title: seg.title, el, fill: el.lastChild, buffer: el.firstChild };
    });
    chaptersEl.replaceChildren(...chapters.map((c) => c.el));
    renderTime();
    renderBuffer();
  }
  let pendingChapters = [];
  video.addEventListener("loadedmetadata", () => buildChapters(pendingChapters));

  const chapterAt = (t) => chapters.findLast((c) => t >= c.start) || chapters[0];

  // --- Play state and time ---
  const renderPlay = () => {
    const paused = video.paused || video.ended;
    shell.classList.toggle("paused", paused);
    play.innerHTML = paused ? PLAYER_ICONS.play : PLAYER_ICONS.pause;
    play.setAttribute("aria-label", paused ? "Play (k)" : "Pause (k)");
    big.setAttribute("aria-label", paused ? "Play" : "Pause");
    if (paused) showControls();
  };
  function renderTime() {
    const t = video.currentTime || 0, d = duration();
    const f = d ? t / d : 0;
    for (const c of chapters) {
      const span = c.end - c.start;
      c.fill.style.width = `${span > 0 ? Math.max(0, Math.min(1, (t - c.start) / span)) * 100 : 0}%`;
    }
    thumb.style.left = `${f * 100}%`;
    mini.style.width = `${f * 100}%`;
    now.textContent = formatDuration(t);
    total.textContent = formatDuration(d);
    const current = chapters.length > 1 ? chapterAt(t) : null;
    chapterLabel.textContent = current?.title || "";
    scrub.setAttribute("aria-valuemax", String(Math.round(d)));
    scrub.setAttribute("aria-valuenow", String(Math.round(t)));
    scrub.setAttribute("aria-valuetext", `${now.textContent} of ${total.textContent}`);
  }
  function renderBuffer() {
    const b = video.buffered, d = duration();
    const loaded = b.length && d ? b.end(b.length - 1) : 0;
    for (const c of chapters) {
      const span = c.end - c.start;
      c.buffer.style.width = `${span > 0 ? Math.max(0, Math.min(1, (loaded - c.start) / span)) * 100 : 0}%`;
    }
  }
  video.addEventListener("play", renderPlay);
  video.addEventListener("pause", renderPlay);
  video.addEventListener("ended", renderPlay);
  video.addEventListener("timeupdate", renderTime);
  video.addEventListener("durationchange", () => buildChapters(pendingChapters));
  video.addEventListener("progress", renderBuffer);
  // A new source: chapters are rebuilt once its metadata loads (callers pass new ones via setChapters)
  video.addEventListener("emptied", () => { buildChapters([]); renderPlay(); });
  video.addEventListener("waiting", () => shell.classList.add("loading"));
  for (const ev of ["playing", "canplay", "pause"]) video.addEventListener(ev, () => shell.classList.remove("loading"));

  // A brief icon in the middle when play state changes by click or key
  const flashIcon = (icon) => {
    flash.innerHTML = icon;
    flash.classList.remove("show");
    void flash.offsetWidth;   // restart the animation
    flash.classList.add("show");
  };
  const toggleWithFlash = () => {
    flashIcon(video.paused || video.ended ? PLAYER_ICONS.play : PLAYER_ICONS.pause);
    toggle();
  };

  big.addEventListener("click", toggle);
  play.addEventListener("click", toggle);
  video.addEventListener("click", toggleWithFlash);
  video.addEventListener("dblclick", () => toggleFullscreen());

  // --- Seeking ---
  const seekBubbles = { back: q(".pl-seek-back"), forward: q(".pl-seek-forward") };
  let seekTotal = 0, seekDir = "", seekTimer = 0;
  function seekBy(seconds) {
    if (!duration()) return;
    video.currentTime = Math.max(0, Math.min(duration(), video.currentTime + seconds));
    renderTime();
    // Repeated presses in the same direction add up in the bubble, like YouTube
    const dir = seconds < 0 ? "back" : "forward";
    seekTotal = dir === seekDir ? seekTotal + Math.abs(seconds) : Math.abs(seconds);
    seekDir = dir;
    const bubble = seekBubbles[dir];
    bubble.querySelector("span").textContent = `${dir === "back" ? "−" : "+"}${seekTotal}s`;
    seekBubbles[dir === "back" ? "forward" : "back"].classList.remove("show");
    bubble.classList.add("show");
    clearTimeout(seekTimer);
    seekTimer = setTimeout(() => { bubble.classList.remove("show"); seekDir = ""; seekTotal = 0; }, 700);
    showControls();
  }

  // --- Scrubbing ---
  const timeAt = (clientX) => {
    const r = scrub.getBoundingClientRect();
    return Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * duration();
  };
  const showTip = (clientX) => {
    const t = timeAt(clientX);
    tipTime.textContent = formatDuration(t);
    const c = chapters.length > 1 ? chapterAt(t) : null;
    tipText.textContent = c?.title || "";
    tip.classList.toggle("has-text", !!c?.title);
    // Keep the tooltip inside the player
    const r = scrub.getBoundingClientRect();
    const half = tip.offsetWidth / 2;
    tip.style.left = `${Math.max(half, Math.min(r.width - half, clientX - r.left))}px`;
    chapters.forEach((ch) => ch.el.classList.toggle("hover", ch === c));
  };
  scrub.addEventListener("pointerdown", (e) => {
    if (!duration()) return;
    scrub.setPointerCapture(e.pointerId);
    shell.classList.add("scrubbing");
    video.currentTime = timeAt(e.clientX);
    renderTime();
  });
  scrub.addEventListener("pointermove", (e) => {
    if (!duration()) return;
    showTip(e.clientX);
    if (shell.classList.contains("scrubbing")) { video.currentTime = timeAt(e.clientX); renderTime(); }
  });
  scrub.addEventListener("pointerleave", () => chapters.forEach((ch) => ch.el.classList.remove("hover")));
  const endScrub = () => shell.classList.remove("scrubbing");
  scrub.addEventListener("pointerup", endScrub);
  scrub.addEventListener("pointercancel", endScrub);

  // --- Volume ---
  const renderVolume = () => {
    const silent = video.muted || video.volume === 0;
    mute.innerHTML = silent ? PLAYER_ICONS.muted : PLAYER_ICONS.volume;
    mute.setAttribute("aria-label", silent ? "Unmute (m)" : "Mute (m)");
    vol.value = silent ? 0 : video.volume;
    vol.style.setProperty("--level", `${(silent ? 0 : video.volume) * 100}%`);
  };
  mute.addEventListener("click", () => {
    video.muted = !video.muted;
    if (!video.muted && video.volume === 0) video.volume = 1;
  });
  vol.addEventListener("input", () => {
    video.volume = Number(vol.value);
    video.muted = video.volume === 0;
  });
  video.addEventListener("volumechange", renderVolume);

  // --- Captions ---
  let captionsOn = false;
  const renderCaptions = () => {
    const tracks = [...video.textTracks];
    cc.hidden = tracks.length === 0;
    tracks.forEach((t) => (t.mode = captionsOn ? "showing" : "hidden"));
    cc.classList.toggle("on", captionsOn);
    cc.setAttribute("aria-pressed", String(captionsOn));
  };
  const toggleCaptions = () => { if (!cc.hidden) { captionsOn = !captionsOn; renderCaptions(); } };
  cc.addEventListener("click", toggleCaptions);
  video.textTracks.addEventListener("addtrack", renderCaptions);
  video.textTracks.addEventListener("removetrack", renderCaptions);
  video.addEventListener("loadedmetadata", renderCaptions);

  // --- Speed ---
  speed.addEventListener("click", () => {
    video.playbackRate = SPEEDS[(SPEEDS.indexOf(video.playbackRate) + 1) % SPEEDS.length] || 1;
  });
  video.addEventListener("ratechange", () => { speed.textContent = `${video.playbackRate}x`; });

  // --- Fullscreen ---
  function toggleFullscreen() {
    if (document.fullscreenElement === shell) document.exitFullscreen();
    else shell.requestFullscreen?.().catch(() => {});
  }
  full.addEventListener("click", toggleFullscreen);
  document.addEventListener("fullscreenchange", () => {
    const on = document.fullscreenElement === shell;
    shell.classList.toggle("fullscreen", on);
    full.innerHTML = on ? PLAYER_ICONS.exit : PLAYER_ICONS.enter;
    full.setAttribute("aria-label", on ? "Exit full screen (f)" : "Full screen (f)");
  });

  // --- Auto-hiding controls ---
  let idleTimer = 0;
  function showControls() {
    shell.classList.remove("idle");
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      if (!video.paused && !shell.classList.contains("scrubbing")) shell.classList.add("idle");
    }, 2200);
  }
  shell.addEventListener("pointermove", showControls);
  shell.addEventListener("pointerleave", () => { if (!video.paused) shell.classList.add("idle"); });
  shell.addEventListener("focusin", showControls);

  // --- Keyboard ---
  function handleKey(e) {
    const key = e.key.toLowerCase();
    if (key === " " || key === "k") toggleWithFlash();
    else if (key === "arrowright") seekBy(5);
    else if (key === "arrowleft") seekBy(-5);
    else if (key === "l") seekBy(10);
    else if (key === "j") seekBy(-10);
    else if (key === "m") video.muted = !video.muted;
    else if (key === "c") toggleCaptions();
    else if (key === "f") toggleFullscreen();
    else return false;
    showControls();
    return true;
  }
  shell._handleKey = handleKey;

  renderPlay();
  buildChapters([]);
  renderVolume();
  renderCaptions();

  return {
    shell,
    setChapters(list) {
      pendingChapters = list || [];
      buildChapters(pendingChapters);
    },
    setTitle(text) { title.textContent = text || ""; },
  };
}

// Page-wide shortcuts go to the player that's on screen, unless you're typing or
// a control inside another widget has focus
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.target.closest("input, textarea, select, [contenteditable]")) return;
  const key = e.key.toLowerCase();
  if ((key === " " || key === "enter") && e.target.closest("button, a, summary")) return;   // let those activate
  const shell = [...players].find((s) => s.offsetParent !== null || document.fullscreenElement === s);
  if (shell && shell._handleKey(e)) e.preventDefault();
});
