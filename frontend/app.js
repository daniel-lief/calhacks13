"use strict";

const EXAMPLES = [
  "The fast Fourier transform",
  "How vaccines train your immune system",
  "Why the Roman Empire fell",
  "Dijkstra's shortest path algorithm",
  "Supply and demand",
  "How lenses focus light",
  "Why ice floats",
  "The Silk Road",
];

const STEPS = ["writing", "checking", "rendering", "reviewing", "done"];
const ACTIVE = new Set(["queued", ...STEPS.slice(0, 4)]);
const POLL_MS = 1500;

const $ = (sel) => document.querySelector(sel);
const el = {
  form: $("#form"), topic: $("#topic"), submit: $("#submit"), examples: $("#examples"),
  banner: $("#banner"), health: $("#health"),
  job: $("#job"), jobTopic: $("#job-topic"), jobTitle: $("#job-title"), elapsed: $("#job-elapsed"),
  steps: $("#steps"), progressWrap: $("#progress-wrap"), progressBar: $("#progress-bar"), stage: $("#job-stage"),
  player: $("#player"), video: $("#video"), download: $("#download"),
  toggleCode: $("#toggle-code"), codePanel: $("#code-panel"), code: $("#code"), copyCode: $("#copy-code"),
  newVideo: $("#new-video"), failure: $("#failure"), failureMsg: $("#failure-msg"), retry: $("#retry"),
  log: $("#log"), library: $("#library"), libraryEmpty: $("#library-empty"),
};

let current = null;       // job object being shown
let pollTimer = null;
let elapsedTimer = null;
let renderedLogCount = 0;
let loadedVideoUrl = null;
let codeLoadedFor = null;

// --- API ---------------------------------------------------------------------

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? null : res.json();
}

// --- Health ------------------------------------------------------------------

async function checkHealth() {
  try {
    const h = await api("/api/health");
    const pills = [
      ["Claude", h.anthropic], ["FFmpeg", h.ffmpeg], ["LaTeX", h.latex], ["Voice", h.tts],
    ];
    el.health.innerHTML = pills
      .map(([name, ok]) => `<span class="pill ${ok ? "ok" : "bad"}">${name}</span>`)
      .join("") +
      `<span class="pill" title="Claude model and estimated total spend">${escapeHtml(h.model.replace(/^claude-/, ""))} · $${h.total_cost_usd.toFixed(2)} spent</span>`;
    const problems = [];
    if (!h.anthropic) problems.push("No Anthropic API key found — add <code>ANTHROPIC_API_KEY=...</code> to <code>.env</code> and restart the server.");
    if (!h.ffmpeg) problems.push("FFmpeg wasn't found, so videos can't be encoded. Install it and/or set <code>FFMPEG_DIR</code>.");
    if (!h.latex) problems.push("LaTeX wasn't found; equations will fail to render. Install MiKTeX or TeX Live and/or set <code>LATEX_DIR</code>.");
    el.banner.innerHTML = problems.join("<br>");
    el.banner.hidden = problems.length === 0;
  } catch {
    el.health.innerHTML = `<span class="pill bad">Server offline</span>`;
  }
}

// --- Composer ----------------------------------------------------------------

function renderExamples() {
  for (const text of EXAMPLES) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = text;
    b.addEventListener("click", () => { el.topic.value = text; el.topic.focus(); });
    el.examples.appendChild(b);
  }
}

function formPayload() {
  const fd = new FormData(el.form);
  return {
    topic: el.topic.value.trim(),
    length: fd.get("length"),
    quality: fd.get("quality"),
    narration: fd.get("narration") === "on",
    review: fd.get("review") === "on",
    extra: (fd.get("extra") || "").trim(),
  };
}

async function submitJob(payload) {
  el.submit.disabled = true;
  try {
    const job = await api("/api/jobs", { method: "POST", body: JSON.stringify(payload) });
    location.hash = `#/v/${job.id}`;
    refreshLibrary();
  } catch (err) {
    alert(`Couldn't start: ${err.message}`);
  } finally {
    el.submit.disabled = false;
  }
}

el.form.addEventListener("submit", (e) => {
  e.preventDefault();
  const payload = formPayload();
  if (payload.topic.length < 2) return;
  submitJob(payload);
});

// --- Job view ----------------------------------------------------------------

function showJob(id) {
  stopPolling();
  current = null;
  renderedLogCount = 0;
  loadedVideoUrl = null;
  codeLoadedFor = null;
  el.log.innerHTML = "";
  el.codePanel.hidden = true;
  el.toggleCode.textContent = "View ManimGL code";
  el.video.removeAttribute("src");
  el.video.removeAttribute("poster");
  el.video.innerHTML = "";
  el.job.hidden = false;
  el.job.className = "job card";
  el.jobTitle.textContent = "Loading…";
  el.jobTopic.textContent = "";
  poll(id);
  el.job.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function poll(id) {
  try {
    const job = await api(`/api/jobs/${id}`);
    renderJob(job);
    if (ACTIVE.has(job.status)) {
      pollTimer = setTimeout(() => poll(id), POLL_MS);
    } else {
      refreshLibrary();
    }
  } catch (err) {
    el.jobTitle.textContent = "Video not found";
    el.stage.textContent = err.message;
  }
}

function stopPolling() {
  clearTimeout(pollTimer);
  pollTimer = null;
}

function renderJob(job) {
  const statusChanged = !current || current.status !== job.status;
  current = job;
  el.job.className = `job card ${job.status}`;
  el.jobTopic.textContent = job.title ? job.topic : "Topic";
  el.jobTitle.textContent = job.title || job.topic;

  // Steps
  const idx = job.status === "queued" ? -1 : STEPS.indexOf(job.status);
  el.steps.querySelectorAll("li").forEach((li, i) => {
    const step = li.dataset.step;
    li.className = "";
    if (step === "reviewing" && !job.options.review) li.classList.add("skipped");
    if (job.status === "failed") return;
    if (i < idx || job.status === "done") li.classList.add("done");
    else if (i === idx) li.classList.add("active");
  });

  // Progress
  const active = ACTIVE.has(job.status);
  el.progressWrap.hidden = !active;
  el.progressBar.style.width = `${Math.round(job.progress * 100)}%`;
  el.stage.textContent = job.status === "queued"
    ? `Waiting in queue${job.queue_position > 1 ? ` (#${job.queue_position})` : ""}`
    : job.stage;

  // Elapsed
  clearInterval(elapsedTimer);
  const tick = () => {
    const end = job.finished_at || Date.now() / 1000;
    const cost = job.cost_usd ? ` · $${job.cost_usd.toFixed(2)}` : "";
    const model = job.model ? ` · ${job.model.replace(/^claude-/, "")}` : "";
    el.elapsed.textContent = `${formatDuration(end - job.created_at)}${cost}${model}`;
  };
  tick();
  if (active) elapsedTimer = setInterval(tick, 1000);

  // Player: show the first cut as soon as it exists, swap in the polished cut later
  if (job.video_url && job.video_url !== loadedVideoUrl) {
    loadedVideoUrl = job.video_url;
    el.video.innerHTML = job.captions_url
      ? `<track kind="captions" srclang="en" label="English" src="${job.captions_url}" default>`
      : "";
    el.video.poster = job.thumbnail_url || "";
    el.video.src = job.video_url;
    el.download.href = job.video_url;
    el.download.download = `${slug(job.title || job.topic)}.mp4`;
    codeLoadedFor = null;
    if (!el.codePanel.hidden) loadCode();
  }
  el.player.hidden = !job.video_url;
  el.newVideo.hidden = active;

  // Failure
  el.failure.hidden = job.status !== "failed";
  if (job.status === "failed") {
    el.failureMsg.textContent = job.error || "Something went wrong.";
    el.retry.hidden = false;
  }

  // Log (append-only)
  const logs = job.logs || [];
  for (const entry of logs.slice(renderedLogCount)) {
    const li = document.createElement("li");
    li.className = entry.kind;
    const t = document.createElement("time");
    t.textContent = formatDuration(entry.t);
    const span = document.createElement("span");
    span.textContent = entry.msg;
    li.append(t, span);
    el.log.appendChild(li);
  }
  if (logs.length > renderedLogCount) el.log.scrollTop = el.log.scrollHeight;
  renderedLogCount = logs.length;

  if (statusChanged) markCurrentTile();
}

async function loadCode() {
  if (!current?.code_url || codeLoadedFor === current.video_url) return;
  try {
    const res = await fetch(`${current.code_url}?v=${Date.now()}`);
    const text = await res.text();
    el.code.innerHTML = highlightPython(text);
    el.code.dataset.raw = text;
    codeLoadedFor = current.video_url;
  } catch {
    el.code.textContent = "Couldn't load the code.";
  }
}

el.toggleCode.addEventListener("click", async () => {
  const show = el.codePanel.hidden;
  el.codePanel.hidden = !show;
  el.toggleCode.textContent = show ? "Hide code" : "View ManimGL code";
  if (show) await loadCode();
});

el.copyCode.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(el.code.dataset.raw || "");
    el.copyCode.textContent = "Copied";
    setTimeout(() => (el.copyCode.textContent = "Copy"), 1500);
  } catch { /* clipboard unavailable */ }
});

el.newVideo.addEventListener("click", () => {
  location.hash = "#/";
  el.topic.value = "";
  el.topic.focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

el.retry.addEventListener("click", () => {
  if (!current) return;
  submitJob({ topic: current.topic, ...current.options });
});

// --- Library -----------------------------------------------------------------

let libraryTimer = null;

async function refreshLibrary() {
  clearTimeout(libraryTimer);
  let jobs = [];
  try { jobs = await api("/api/jobs"); } catch { return; }
  el.library.innerHTML = "";
  el.libraryEmpty.hidden = jobs.length > 0;
  for (const job of jobs) el.library.appendChild(tile(job));
  markCurrentTile();
  if (jobs.some((j) => ACTIVE.has(j.status))) libraryTimer = setTimeout(refreshLibrary, 5000);
}

function tile(job) {
  const a = document.createElement("a");
  a.className = "tile";
  a.href = `#/v/${job.id}`;
  a.dataset.id = job.id;

  const thumb = document.createElement("div");
  thumb.className = "thumb";
  if (job.thumbnail_url) thumb.style.backgroundImage = `url("${job.thumbnail_url}")`;
  else thumb.textContent = ACTIVE.has(job.status) ? "In progress…" : job.status === "failed" ? "Failed" : "";

  const body = document.createElement("div");
  body.className = "tile-body";
  const title = document.createElement("p");
  title.className = "tile-title";
  title.textContent = job.title || job.topic;
  const meta = document.createElement("div");
  meta.className = "tile-meta";
  const when = document.createElement("span");
  when.textContent = timeAgo(job.created_at);
  meta.appendChild(when);
  if (job.status !== "done") {
    const badge = document.createElement("span");
    badge.className = `badge ${job.status === "failed" ? "failed" : "active"}`;
    badge.textContent = job.status === "failed" ? "failed" : job.status;
    meta.appendChild(badge);
  }
  body.append(title, meta);
  a.append(thumb, body);

  if (!ACTIVE.has(job.status)) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove";
    remove.title = "Delete video";
    remove.setAttribute("aria-label", "Delete video");
    remove.textContent = "×";
    remove.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!confirm(`Delete “${job.title || job.topic}”?`)) return;
      try {
        await api(`/api/jobs/${job.id}`, { method: "DELETE" });
        if (current?.id === job.id) location.hash = "#/";
        refreshLibrary();
      } catch (err) { alert(err.message); }
    });
    a.appendChild(remove);
  }
  return a;
}

function markCurrentTile() {
  el.library.querySelectorAll(".tile").forEach((t) => {
    t.classList.toggle("current", t.dataset.id === current?.id);
  });
}

// --- Routing -----------------------------------------------------------------

function route() {
  const match = location.hash.match(/^#\/v\/([\w-]+)/);
  if (match) {
    if (current?.id !== match[1] || !pollTimer) showJob(match[1]);
  } else {
    stopPolling();
    clearInterval(elapsedTimer);
    current = null;
    el.job.hidden = true;
    el.video.pause();
    markCurrentTile();
  }
}
window.addEventListener("hashchange", route);

// --- Helpers -----------------------------------------------------------------

function formatDuration(seconds) {
  seconds = Math.max(0, Math.round(seconds));
  const m = Math.floor(seconds / 60);
  const s = String(seconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function timeAgo(ts) {
  const s = Date.now() / 1000 - ts;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(ts * 1000).toLocaleDateString();
}

function slug(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "explainer";
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// Tiny single-pass highlighter: comments, strings, keywords, numbers
function highlightPython(src) {
  const re = /(#[^\n]*)|([rRbBfF]{0,2}(?:"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'))|\b(def|class|return|for|in|if|elif|else|while|with|as|import|from|lambda|and|or|not|None|True|False|self|yield|try|except|pass|break|continue)\b|\b(\d+(?:\.\d+)?)\b/g;
  let out = "";
  let last = 0;
  for (const m of src.matchAll(re)) {
    out += escapeHtml(src.slice(last, m.index));
    const cls = m[1] ? "com" : m[2] ? "str" : m[3] ? "kw" : "num";
    out += `<span class="tok-${cls}">${escapeHtml(m[0])}</span>`;
    last = m.index + m[0].length;
  }
  return out + escapeHtml(src.slice(last));
}

// --- Boot --------------------------------------------------------------------

renderExamples();
checkHealth();
refreshLibrary();
route();
