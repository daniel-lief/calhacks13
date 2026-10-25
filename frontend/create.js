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

const STEPS = ["researching", "writing", "checking", "rendering", "reviewing", "done"];

const el = {
  form: $("#form"), topic: $("#topic"), submit: $("#submit"), submitBottom: $("#submit-bottom"), examples: $("#examples"),
  toggleOptions: $("#toggle-options"), options: $("#options"), banner: $("#banner"), voiceGrid: $("#voice-grid"), themeGrid: $("#theme-grid"),
  pdfInput: $("#pdf-input"), pdfChosen: $("#pdf-chosen"), pdfRemove: $("#pdf-remove"), pdfError: $("#pdf-error"),
  job: $("#job"), jobTopic: $("#job-topic"), jobTitle: $("#job-title"), elapsed: $("#job-elapsed"),
  steps: $("#steps"), progressWrap: $("#progress-wrap"), progressBar: $("#progress-bar"), stage: $("#job-stage"),
  player: $("#player"), video: $("#video"), ready: $("#job-ready"),
  failure: $("#failure"), failureMsg: $("#failure-msg"), retry: $("#retry"), log: $("#log"),
  jobTags: $("#job-tags"), tagList: $("#job-tag-list"), editTags: $("#edit-tags"),
  tagForm: $("#tag-form"), tagInput: $("#tag-input"), tagCancel: $("#tag-cancel"),
  research: $("#job-research"), researchMessage: $("#research-message"), researchSources: $("#research-sources"),
};

const jobPlayer = enhancePlayer(el.video);

let current = null;       // job object being shown
let jobUnsubs = [];       // live Convex queries for the job being shown
let queuePosition = 0;
let elapsedTimer = null;
let renderedLogCount = 0;
let loadedVideoUrl = null;

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
    research: fd.get("research") === "on",
    public: fd.get("public") === "on",
    voice: fd.get("voice") || "",
    theme: fd.get("theme") || "bubble",
    extra: (fd.get("extra") || "").trim(),
  };
}

// --- PDF context ---------------------------------------------------------------
// The PDF is private context for Claude. It goes to our own server's memory as the raw
// request body (so not even its filename leaves the browser), never to Convex.

const PDF_MAX_BYTES = 20 * 1024 * 1024;
let pdfFile = null;

function setPdf(file) {
  el.pdfError.textContent = "";
  if (file && !(file.type === "application/pdf" || /\.pdf$/i.test(file.name))) {
    el.pdfError.textContent = "That file isn't a PDF";
    file = null;
  } else if (file && file.size > PDF_MAX_BYTES) {
    el.pdfError.textContent = "PDFs can be up to 20 MB and 50 pages";
    file = null;
  }
  pdfFile = file;
  el.pdfInput.value = "";
  el.pdfChosen.hidden = el.pdfRemove.hidden = !file;
  const size = file && (file.size < 1024 * 1024 ? `${Math.max(1, Math.round(file.size / 1024))} KB`
    : `${(file.size / 1024 / 1024).toFixed(1)} MB`);
  el.pdfChosen.textContent = file ? `${file.name} (${size})` : "";
}

el.pdfInput.addEventListener("change", () => setPdf(el.pdfInput.files[0] || null));
el.pdfRemove.addEventListener("click", () => setPdf(null));

async function uploadPdf(file) {
  const send = async (refresh) => fetch("/api/attachments", {
    method: "POST",
    headers: { "Content-Type": "application/pdf", Authorization: `Bearer ${await authToken({ refresh })}` },
    body: file,
  });
  let res = await send(false);
  if (res.status === 401) res = await send(true);  // the short-lived session token may have just expired
  if (!res.ok) {
    let detail = "Couldn't upload the PDF";
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return (await res.json()).token;
}

async function submitJob(payload) {
  if (el.submit.disabled || !requireSignIn("Sign in to make videos")) return;
  el.submit.disabled = el.submitBottom.disabled = true;
  try {
    if (pdfFile) payload = { ...payload, attachment: await uploadPdf(pdfFile) };
    const id = await call("mutation", "videos:create", payload);
    setPdf(null);
    location.hash = `#/v/${id}`;
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
  if (current?.id === id && jobUnsubs.length) return;
  stopJob();
  stopPreview();
  renderedLogCount = 0;
  loadedVideoUrl = null;
  el.log.innerHTML = "";
  el.player.hidden = true;
  el.ready.hidden = true;
  el.video.removeAttribute("src");
  el.video.removeAttribute("poster");
  el.video.innerHTML = "";
  el.form.hidden = true;
  el.job.hidden = false;
  el.job.className = "job";
  el.jobTitle.textContent = "Loading";
  el.jobTopic.textContent = "";
  el.jobTags.hidden = true;
  el.research.hidden = true;
  closeTagEditor();
  // Live: progress, log lines and the finished video arrive as the worker reports them
  queuePosition = 0;
  jobUnsubs = [
    watch("videos:get", { id }, (job) => {
      if (job) renderJob(job);
      else showMissingJob();
    }, showMissingJob),
    watch("videos:logs", { id }, renderLogs),
    watch("videos:queuePosition", { id }, (n) => {
      queuePosition = n;
      if (current) renderJob(current);
    }),
  ];
}

function showMissingJob() {
  el.jobTitle.textContent = "Video not found";
  el.stage.textContent = "It may have been deleted, or it belongs to someone else.";
  el.progressWrap.hidden = false;
}

function stopJob() {
  jobUnsubs.forEach((stop) => stop());
  jobUnsubs = [];
  clearInterval(elapsedTimer);
  current = null;
  el.video.pause();
}

// --- Job view ----------------------------------------------------------------

function renderJob(job) {
  current = job;
  el.job.className = `job ${job.status}`;
  el.jobTopic.textContent = STATUS_LABEL[job.status] || job.status;
  el.jobTitle.textContent = job.title || job.topic;
  renderTags(job);
  renderResearch(job);

  // Steps
  const idx = job.status === "queued" ? -1 : STEPS.indexOf(job.status);
  el.steps.querySelectorAll("li").forEach((li, i) => {
    const step = li.dataset.step;
    li.className = "";
    if (step === "reviewing" && !job.options.review) li.classList.add("skipped");
    if (step === "researching" && (job.options.research === false || ["skipped", "unavailable"].includes(job.research?.status))) li.classList.add("skipped");
    if (job.status === "failed") return;
    if (i < idx || job.status === "done") li.classList.add("done");
    else if (i === idx) li.classList.add("active");
  });

  // Progress
  const active = ACTIVE.has(job.status);
  el.progressWrap.hidden = !active;
  el.progressBar.style.width = `${Math.round(job.progress * 100)}%`;
  el.stage.textContent = job.status === "queued"
    ? `Waiting in queue${queuePosition > 1 ? ` (#${queuePosition})` : ""}`
    : job.stage;

  // Elapsed
  clearInterval(elapsedTimer);
  const tick = () => {
    const end = job.finished_at || Date.now() / 1000;
    el.elapsed.textContent = formatDuration(end - job.created_at);
  };
  tick();
  if (active) elapsedTimer = setInterval(tick, 1000);

  // First-cut files can arrive during review. Attach media only after the final result.
  const ready = job.status === "done" && !!job.video_url;
  el.ready.hidden = !ready;
  el.player.hidden = !ready;
  if (!ready && loadedVideoUrl) {
    el.video.pause();
    el.video.removeAttribute("src");
    el.video.removeAttribute("poster");
    el.video.innerHTML = "";
    el.video.load();
    loadedVideoUrl = null;
  }
  if (ready && job.video_url !== loadedVideoUrl) {
    loadedVideoUrl = job.video_url;
    el.video.innerHTML = job.captions_url
      ? `<track kind="captions" srclang="en" label="English" src="${job.captions_url}" default>`
      : "";
    el.video.poster = job.thumbnail_url || "";
    el.video.src = job.video_url;
    jobPlayer.setTitle(job.title || job.topic);
    jobPlayer.setChapters(job.chapters);
  }

  // Failure
  el.failure.hidden = job.status !== "failed";
  if (job.status === "failed") el.failureMsg.textContent = job.error || "Something went wrong.";

}

// "Behind the scenes": the newest 300 lines, appended as they arrive
function renderLogs(logs) {
  if (logs.length < renderedLogCount) {
    el.log.innerHTML = "";
    renderedLogCount = 0;
  }
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

// --- Tags ----------------------------------------------------------------------

function renderResearch(job) {
  const research = job.research;
  el.research.hidden = !research || !research.status || research.status === "skipped";
  el.researchMessage.textContent = research?.message || "";
  const sources = (research?.sources || []).filter(source =>
    /^https:\/\/www\.youtube\.com\/watch\?v=[A-Za-z0-9_-]{11}$/.test(source.url));
  el.researchSources.replaceChildren(...sources.map(source => {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = source.title;
    li.appendChild(link);
    if (source.channel) li.append(` · ${source.channel}`);
    return li;
  }));
}

function renderTags(job) {
  const tags = job.tags || [];
  el.jobTags.hidden = tags.length === 0 && (!job.ownedByMe || job.status !== "done");
  el.tagList.replaceChildren(...topTags(job).map((t) => {
    const link = document.createElement("a");
    link.className = "chip";
    link.href = `#/discover?tag=${encodeURIComponent(t)}`;
    link.textContent = t;
    return link;
  }));
  el.editTags.hidden = !job.ownedByMe || !el.tagForm.hidden;
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
    current.tags = await call("mutation", "videos:setTags", { id: current.id, tags });
    closeTagEditor();
  } catch (err) { alert(`Couldn't save tags: ${err.message}`); }
});

el.retry.addEventListener("click", () => {
  if (!current) return;
  submitJob({ topic: current.topic, ...current.options, public: current.public });
});
