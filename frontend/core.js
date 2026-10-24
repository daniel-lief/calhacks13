"use strict";

// Shared by every screen: API access, formatting helpers, likes, and the page
// atmosphere (grain, preloader, text reveals, cursor).

const ACTIVE = new Set(["queued", "writing", "checking", "rendering", "reviewing"]);
const STATUS_LABEL = {
  queued: "Queued", writing: "Writing the script", checking: "Test run", rendering: "Rendering",
  reviewing: "Reviewing frames", done: "Ready", failed: "Failed",
};

const $ = (sel) => document.querySelector(sel);

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
  const lines = document.querySelectorAll(".health");
  const setLines = (text, bad) => lines.forEach((n) => {
    n.textContent = text;
    n.classList.toggle("health-bad", bad);
  });
  try {
    const h = await api("/api/health");
    document.querySelectorAll(".footer-meta").forEach((n) => {
      n.textContent = `Animai - ${h.model.replace(/^claude-/, "")} - $${h.total_cost_usd.toFixed(2)} spent`;
    });
    const missing = [["Claude", h.anthropic], ["FFmpeg", h.ffmpeg], ["LaTeX", h.latex], ["Voice", h.tts]]
      .filter(([, ok]) => !ok).map(([name]) => name);
    setLines(missing.length ? `Not available: ${missing.join(", ")}` : "Claude, FFmpeg, LaTeX and voice are ready", missing.length > 0);
    return h;
  } catch {
    setLines("Server offline", true);
    return null;
  }
}

// --- Likes (who liked what is remembered per browser; counts live on the server)

const likedIds = new Set(readLiked());

function readLiked() {
  try { return JSON.parse(localStorage.getItem("animai-liked") || "[]"); } catch { return []; }
}

async function setLiked(job, liked) {
  if (liked) likedIds.add(job.id); else likedIds.delete(job.id);
  try { localStorage.setItem("animai-liked", JSON.stringify([...likedIds])); } catch { /* storage blocked */ }
  try {
    const updated = await api(`/api/jobs/${job.id}/like`, { method: "POST", body: JSON.stringify({ liked }) });
    job.likes = updated.likes;
  } catch { /* keep the optimistic state */ }
  return job.likes;
}

const viewedIds = new Set();   // count each video once per visit

function countView(job) {
  if (viewedIds.has(job.id)) return;
  viewedIds.add(job.id);
  job.views = (job.views || 0) + 1;
  api(`/api/jobs/${job.id}/view`, { method: "POST" }).catch(() => {});
}

const HEART = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 8 3.6 4.5 7.1 4.5c2 0 3.6 1.1 4.9 2.8 1.3-1.7 2.9-2.8 4.9-2.8 3.5 0 5.7 3.5 4.4 6.8-1.8 4.6-9.3 9.2-9.3 9.2z"/></svg>`;
const EYE = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>`;

// --- Formatting ----------------------------------------------------------------

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

function compact(n) {
  return n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n || 0);
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function author(job) {
  return job.sample ? "@animai" : "@you";
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

// --- Atmosphere ----------------------------------------------------------------

function paintGrain() {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const ctx = c.getContext("2d");
  const img = ctx.createImageData(256, 256);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = Math.random() * 255;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  $(".noise").style.backgroundImage = `url(${c.toDataURL()})`;
}

function splitText() {
  for (const node of document.querySelectorAll(".split")) {
    const words = node.textContent.trim().split(/\s+/);
    node.replaceChildren(...words.flatMap((w, i) => {
      const wrap = document.createElement("span");
      wrap.className = "word-wrapper";
      const word = document.createElement("span");
      word.className = "word";
      word.style.setProperty("--anim-index", i);
      word.textContent = w;
      wrap.appendChild(word);
      return i < words.length - 1 ? [wrap, " "] : [wrap];
    }));
    node.classList.add("is-split");
  }
  for (const node of document.querySelectorAll(".blur-anim")) {
    const label = node.textContent;
    node.setAttribute("aria-label", label);
    node.replaceChildren(...[...label].map((ch, i) => {
      const span = document.createElement("span");
      span.className = "char";
      span.setAttribute("aria-hidden", "true");
      span.style.setProperty("--anim-index", i);
      span.textContent = ch;
      return span;
    }));
    if (node.dataset.delay) node.style.setProperty("--anim-delay", `${node.dataset.delay}s`);
    node.classList.add("is-split");
  }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) e.target.classList.toggle("is-visible", e.isIntersecting);
  }, { threshold: 0.3 });
  document.querySelectorAll(".split, .blur-anim").forEach((n) => io.observe(n));
}

// Counts to 100 on the landing page; skipped when the app opens straight to a screen
function preload(full) {
  const count = $("#preloader-count");
  const preloader = $("#preloader");
  const finish = () => {
    document.body.dataset.preloading = "false";
    preloader.remove();
    window.Scene.refresh();
  };
  if (!full) return finish();
  const start = performance.now();
  const step = (now) => {
    const p = Math.min(1, (now - start) / 1400);
    count.textContent = Math.round(p * p * (3 - 2 * p) * 100);
    if (p < 1) return requestAnimationFrame(step);
    preloader.dataset.dismissing = "true";
    setTimeout(finish, 500);
  };
  document.fonts.ready.then(() => requestAnimationFrame(step));
}

function customCursor() {
  if (!matchMedia("(pointer: fine)").matches) return;
  const cursor = $("#cursor");
  const head = cursor.firstElementChild;
  document.documentElement.classList.add("has-custom-cursor");
  addEventListener("pointermove", (e) => {
    head.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
    cursor.dataset.visible = "true";
    cursor.dataset.hover = String(!!e.target.closest("a, button, input, textarea, label, summary, video"));
  });
  document.addEventListener("pointerleave", () => { cursor.dataset.visible = "false"; });
}
