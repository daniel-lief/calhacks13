"use strict";

// Create screen: the topic composer and, once a video is started, its progress
// and player. Both live inside the particle frame.

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
const POLL_MS = 1500;

const el = {
  form: $("#form"), topic: $("#topic"), submit: $("#submit"), submitBottom: $("#submit-bottom"), examples: $("#examples"),
  toggleOptions: $("#toggle-options"), options: $("#options"), banner: $("#banner"), voiceGrid: $("#voice-grid"), themeGrid: $("#theme-grid"),
  job: $("#job"), jobTopic: $("#job-topic"), jobTitle: $("#job-title"), elapsed: $("#job-elapsed"),
  steps: $("#steps"), progressWrap: $("#progress-wrap"), progressBar: $("#progress-bar"), stage: $("#job-stage"),
  player: $("#player"), video: $("#video"), download: $("#download"), togglePublic: $("#toggle-public"),
  toggleCode: $("#toggle-code"), codePanel: $("#code-panel"), code: $("#code"), copyCode: $("#copy-code"),
  newVideo: $("#new-video"), failure: $("#failure"), failureMsg: $("#failure-msg"), retry: $("#retry"),
  failureNew: $("#failure-new"), log: $("#log"),
  jobTags: $("#job-tags"), tagList: $("#job-tag-list"), editTags: $("#edit-tags"),
  tagForm: $("#tag-form"), tagInput: $("#tag-input"), tagCancel: $("#tag-cancel"),
};

const jobPlayer = enhancePlayer(el.video);

let current = null;       // job object being shown
let pollTimer = null;
let elapsedTimer = null;
let renderedLogCount = 0;
let loadedVideoUrl = null;
let codeLoadedFor = null;

// --- Composer ----------------------------------------------------------------

function renderExamples() {
  const picks = [EXAMPLES[Math.floor(Math.random() * EXAMPLES.length)], "Explain Bubble Sort"];
  el.examples.replaceChildren("or try ");
  picks.forEach((text, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    b.addEventListener("click", () => { el.topic.value = text; el.topic.focus(); });
    el.examples.append(b, i === 0 ? " or " : "");
  });
}

// --- Color themes ------------------------------------------------------------

async function loadThemes() {
  let data;
  try { data = await api("/api/themes"); }
  catch {
    el.themeGrid.textContent = "Using Peach. Other palettes couldn't load; refresh to try again.";
    return;
  }
  el.themeGrid.replaceChildren(...data.themes.map(t => {
    const card = document.createElement("label");
    card.className = "theme-card";
    card.title = t.description;
    const input = document.createElement("input");
    Object.assign(input, {type:"radio", name:"theme", value:t.id, checked:t.id === data.default});
    input.setAttribute("aria-label", `${t.name} color theme`);
    const preview = document.createElement("span");
    preview.className = "theme-preview";
    preview.setAttribute("aria-hidden", "true");
    preview.style.setProperty("--preview-bg", t.colors.background);
    preview.style.setProperty("--preview-end", t.colors.backdrop_color);
    preview.style.setProperty("--preview-surface", t.colors.surface);
    preview.style.setProperty("--preview-text", t.colors.text);
    preview.style.setProperty("--preview-accent", t.colors.accent);
    preview.innerHTML = '<span class="theme-preview-title">Aa</span><span class="theme-preview-panel"></span><span class="theme-preview-dot"></span>';
    const bars = document.createElement("span");
    bars.className = "theme-preview-bars";
    t.colors.palette.slice(0, 5).forEach((color, i) => {
      const bar = document.createElement("i");
      bar.style.background = color;
      bar.style.height = `${[45, 75, 55, 90, 65][i]}%`;
      bars.appendChild(bar);
    });
    preview.appendChild(bars);
    const name = document.createElement("span");
    name.className = "theme-name";
    name.textContent = t.name;
    card.append(input, preview, name);
    return card;
  }));
}

// --- Voices ------------------------------------------------------------------

const voicePreview = new Audio();
let previewing = null;   // the preview button whose sample is playing

async function loadVoices() {
  let data;
  try { data = await api("/api/voices"); } catch { return; }
  el.voiceGrid.replaceChildren(...data.voices.map((v) => {
    const card = document.createElement("label");
    card.className = "voice-card";
    const input = document.createElement("input");
    Object.assign(input, { type: "radio", name: "voice", value: v.id, checked: v.id === data.default });
    const text = document.createElement("span");
    text.className = "voice-text";
    text.innerHTML = `<span class="voice-name"></span><span class="voice-meta"></span>`;
    text.firstChild.textContent = v.name;
    text.lastChild.textContent = `${v.accent} - ${v.description}`;
    const play = document.createElement("button");
    play.type = "button";
    play.className = "voice-play link-button muted";
    play.textContent = "Play sample";
    play.setAttribute("aria-label", `Play a sample of ${v.name}`);
    play.addEventListener("click", (e) => {
      e.preventDefault();   // previewing doesn't pick the voice
      togglePreview(play, v.id);
    });
    card.append(input, text, play);
    return card;
  }));
}

function togglePreview(button, voiceId) {
  const same = previewing === button;
  stopPreview();
  if (same) return;
  previewing = button;
  button.textContent = "Loading";
  voicePreview.src = `/api/voices/${encodeURIComponent(voiceId)}/preview`;
  voicePreview.play()
    .then(() => { if (previewing === button) button.textContent = "Stop"; })
    .catch(() => { if (previewing === button) { button.textContent = "Couldn't play"; previewing = null; } });
}

function stopPreview() {
  voicePreview.pause();
  if (previewing) previewing.textContent = "Play sample";
  previewing = null;
}
voicePreview.addEventListener("ended", stopPreview);

function showHealthBanner(h) {
  const problems = [];
  if (!h) problems.push("The server isn't responding. Start it with <code>.venv\\Scripts\\python -m backend</code>.");
  else {
    if (!h.anthropic) problems.push("No Anthropic API key found. Add <code>ANTHROPIC_API_KEY=...</code> to <code>.env</code> and restart the server.");
    if (!h.ffmpeg) problems.push("FFmpeg wasn't found, so videos can't be encoded. Install it and/or set <code>FFMPEG_DIR</code>.");
    if (!h.latex) problems.push("LaTeX wasn't found, so equations will fail to render. Install MiKTeX or TeX Live and/or set <code>LATEX_DIR</code>.");
  }
  el.banner.innerHTML = problems.join("<br>");
  el.banner.hidden = problems.length === 0;
}

el.toggleOptions.addEventListener("click", () => {
  const show = el.options.hidden;
  el.options.hidden = !show;
  el.toggleOptions.setAttribute("aria-expanded", String(show));
  el.toggleOptions.textContent = show ? "Hide options" : "Options";
});

function formPayload() {
  const fd = new FormData(el.form);
  return {
    topic: el.topic.value.trim(),
    length: fd.get("length"),
    quality: fd.get("quality"),
    narration: fd.get("narration") === "on",
    review: fd.get("review") === "on",
    public: fd.get("public") === "on",
    voice: fd.get("voice") || "",
    theme: fd.get("theme") || "bubble",
    extra: (fd.get("extra") || "").trim(),
  };
}

async function submitJob(payload) {
  if (el.submit.disabled) return;
  el.submit.disabled = el.submitBottom.disabled = true;
  try {
    const job = await api("/api/jobs", { method: "POST", body: JSON.stringify(payload) });
    location.hash = `#/v/${job.id}`;
  } catch (err) {
    alert(`Couldn't start: ${err.message}`);
  } finally {
    el.submit.disabled = el.submitBottom.disabled = false;
  }
}

el.form.addEventListener("submit", (e) => {
  e.preventDefault();
  const payload = formPayload();
  if (payload.topic.length < 2) return;
  submitJob(payload);
});

// --- Entering and leaving the screen -------------------------------------------

function showComposer() {
  stopJob();
  stopPreview();
  el.job.hidden = true;
  el.form.hidden = false;
  el.topic.focus({ preventScroll: true });
}

function showJob(id) {
  if (current?.id === id && pollTimer) return;
  stopJob();
  stopPreview();
  renderedLogCount = 0;
  loadedVideoUrl = null;
  codeLoadedFor = null;
  el.log.innerHTML = "";
  el.codePanel.hidden = true;
  el.toggleCode.textContent = "View ManimGL code";
  el.video.removeAttribute("src");
  el.video.removeAttribute("poster");
  el.video.innerHTML = "";
  el.form.hidden = true;
  el.job.hidden = false;
  el.job.className = "job";
  el.jobTitle.textContent = "Loading";
  el.jobTopic.textContent = "";
  el.jobTags.hidden = true;
  closeTagEditor();
  poll(id);
}

function stopJob() {
  clearTimeout(pollTimer);
  pollTimer = null;
  clearInterval(elapsedTimer);
  current = null;
  el.video.pause();
}

// --- Job view ----------------------------------------------------------------

async function poll(id) {
  try {
    const job = await api(`/api/jobs/${id}`);
    renderJob(job);
    pollTimer = ACTIVE.has(job.status) ? setTimeout(() => poll(id), POLL_MS) : null;
  } catch (err) {
    el.jobTitle.textContent = "Video not found";
    el.stage.textContent = err.message;
  }
}

function renderJob(job) {
  current = job;
  el.job.className = `job ${job.status}`;
  el.jobTopic.textContent = STATUS_LABEL[job.status] || job.status;
  el.jobTitle.textContent = job.title || job.topic;
  renderTags(job);

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
    el.elapsed.textContent = formatDuration(end - job.created_at);
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
    jobPlayer.setTitle(job.title || job.topic);
    jobPlayer.setChapters(job.chapters);
    el.download.href = job.video_url;
    el.download.download = `${slug(job.title || job.topic)}.mp4`;
    codeLoadedFor = null;
    if (!el.codePanel.hidden) loadCode();
  }
  el.player.hidden = !job.video_url;
  el.newVideo.hidden = active;
  el.togglePublic.hidden = job.sample;
  el.togglePublic.textContent = job.public ? "Make private" : "Make public";

  // Failure
  el.failure.hidden = job.status !== "failed";
  if (job.status === "failed") el.failureMsg.textContent = job.error || "Something went wrong.";

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

el.togglePublic.addEventListener("click", async () => {
  if (!current) return;
  try {
    const updated = await api(`/api/jobs/${current.id}`, { method: "PATCH", body: JSON.stringify({ public: !current.public }) });
    current.public = updated.public;
    el.togglePublic.textContent = current.public ? "Make private" : "Make public";
  } catch (err) { alert(err.message); }
});

// --- Tags ----------------------------------------------------------------------

function renderTags(job) {
  const tags = job.tags || [];
  el.jobTags.hidden = tags.length === 0 && (job.sample || job.status !== "done");
  el.tagList.replaceChildren(...topTags(job).map((t) => {
    const link = document.createElement("a");
    link.className = "chip";
    link.href = `#/discover?tag=${encodeURIComponent(t)}`;
    link.textContent = t;
    return link;
  }));
  el.editTags.hidden = job.sample || !el.tagForm.hidden;
  el.editTags.textContent = tags.length ? "Edit tags" : "Add tags";
}

function closeTagEditor() {
  el.tagForm.hidden = true;
  el.tagList.hidden = false;
  if (current) renderTags(current);
}

el.editTags.addEventListener("click", () => {
  el.tagInput.value = (current?.tags || []).join(", ");
  el.tagForm.hidden = false;
  el.tagList.hidden = true;
  el.editTags.hidden = true;
  el.tagInput.focus();
});

el.tagCancel.addEventListener("click", closeTagEditor);
el.tagInput.addEventListener("keydown", (e) => { if (e.key === "Escape") closeTagEditor(); });

el.tagForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!current) return;
  const tags = el.tagInput.value.split(",").map((t) => t.trim()).filter(Boolean);
  try {
    const updated = await api(`/api/jobs/${current.id}`, { method: "PATCH", body: JSON.stringify({ tags }) });
    current.tags = updated.tags;
    closeTagEditor();
  } catch (err) { alert(`Couldn't save tags: ${err.message}`); }
});

function makeAnother() {
  el.topic.value = "";
  location.hash = "#/create";
}
el.newVideo.addEventListener("click", makeAnother);
el.failureNew.addEventListener("click", makeAnother);

el.retry.addEventListener("click", () => {
  if (!current) return;
  submitJob({ topic: current.topic, ...current.options, public: current.public });
});
