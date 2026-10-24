"use strict";

// Routing between the landing page and the app screens, plus the landing
// page's marquee of feed posts.
//
//   #/            landing (scroll story)      #/watch[/id]  vertical scroller
//   #/feed        feed grid                   #/video/<id>  one video, 16:9 watch page
//   #/library     your videos                 #/create      new video
//                                             #/v/<id>      progress of a video you're making

const landing = $("#landing");
const appShell = $("#app");
const screens = {
  feed: $("#screen-feed"), watch: $("#screen-watch"), video: $("#screen-video"),
  create: $("#screen-create"), library: $("#screen-library"),
};
const SCENE_SHAPE = { feed: "dust", watch: "dust", video: "dust", create: "panel", library: "dust" };

let screen = null;   // current app screen, or null on the landing page

function parseRoute() {
  const h = location.hash;
  let m;
  if ((m = h.match(/^#\/watch(?:\/([\w-]+))?/))) return { screen: "watch", id: m[1] };
  if ((m = h.match(/^#\/video\/([\w-]+)/))) return { screen: "video", id: m[1] };
  if ((m = h.match(/^#\/v\/([\w-]+)/))) return { screen: "create", id: m[1] };
  if (h.startsWith("#/feed")) return { screen: "feed" };
  if (h.startsWith("#/create")) return { screen: "create" };
  if (h.startsWith("#/library")) return { screen: "library" };
  return { screen: null };
}

function route() {
  const r = parseRoute();
  const previous = screen;

  if (previous === "watch" && r.screen !== "watch") leaveReel();
  if (previous === "video" && r.screen !== "video") leaveVideo();
  if (previous === "library" && r.screen !== "library") leaveLibrary();
  if (previous === "create" && r.screen !== "create") { stopJob(); stopPreview(); }

  screen = r.screen;
  if (!screen) {
    appShell.hidden = true;
    landing.hidden = false;
    window.Scene.landing();
    if (previous) {
      layoutPlayground();
      window.scrollTo(0, location.hash === "#start" ? document.documentElement.scrollHeight : 0);
    }
    return;
  }

  landing.hidden = true;
  appShell.hidden = false;
  for (const [name, node] of Object.entries(screens)) node.hidden = name !== screen;
  // The watch page belongs to wherever it was opened from
  const nav = screen === "video" ? (["saved", "library"].includes(readFilter().from) ? "library" : "feed") : screen;
  document.querySelectorAll("[data-nav]").forEach((a) => {
    if (a.dataset.nav === nav) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  if (previous !== screen || screen === "video") window.scrollTo(0, 0);

  if (screen === "feed") showFeed();
  else if (screen === "watch") { if (previous !== "watch") showReel(r.id); }
  else if (screen === "video") showVideo(r.id);
  else if (screen === "create") r.id ? showJob(r.id) : showComposer();
  else if (screen === "library") showLibrary();

  // Let the screen lay out before the particles measure it
  requestAnimationFrame(() => window.Scene.show(SCENE_SHAPE[screen]));
}
window.addEventListener("hashchange", route);

// --- Landing marquee ---------------------------------------------------------

const mq = {
  playground: $("#playground"), track: $("#marquee"), kicker: $("#kicker"), closing: $("#closing"),
  markerFlat: $("#marker-flat"), markerLoops: $("#marker-loops"),
};
let travel = 0;

async function loadMarquee() {
  const posts = await loadFeed();
  mq.track.replaceChildren(...posts.map(marqueeTile));
  mq.closing.textContent = posts.length ? "And room for plenty more." : "The first videos will show up here.";
  mq.kicker.hidden = posts.length === 0;
  layoutPlayground();
}

function marqueeTile(job) {
  const a = document.createElement("a");
  a.className = "tile";
  a.href = `#/video/${job.id}`;
  const media = document.createElement("div");
  media.className = "tile-media";
  if (job.thumbnail_url) media.style.backgroundImage = `url("${job.thumbnail_url}")`;
  const caption = document.createElement("div");
  caption.className = "caption";
  const title = document.createElement("p");
  title.className = "t-20";
  title.textContent = job.title || job.topic;
  caption.append(title, statsLine(job));
  a.append(media, caption);
  return a;
}

// The playground is tall; while it scrolls past, the track slides right to left,
// then the closing line takes over. Its height depends on how many posts there are.
function layoutPlayground() {
  if (landing.hidden) return;
  const vh = innerHeight;
  travel = mq.track.children.length ? mq.track.scrollWidth + innerWidth : 0;
  mq.playground.style.height = `${travel + vh * 2}px`;
  mq.markerFlat.style.top = `${travel / 2 + vh / 2}px`;
  mq.markerFlat.hidden = travel === 0;
  mq.markerLoops.style.top = `${travel + vh * 1.1}px`;
  window.Scene.refresh();
  updatePlayground();
}

function updatePlayground() {
  if (landing.hidden) return;
  const offset = -mq.playground.getBoundingClientRect().top;
  mq.track.style.transform = `translate(${innerWidth - Math.max(0, Math.min(travel, offset))}px, -50%)`;
  mq.kicker.dataset.active = String(offset > -innerHeight * 0.2 && offset < travel);
  mq.closing.dataset.active = String(offset > travel + innerHeight * 0.25 && offset < travel + innerHeight * 1.4);
}

addEventListener("scroll", updatePlayground, { passive: true });
addEventListener("resize", layoutPlayground);

$("#monogram").addEventListener("click", (e) => {
  e.preventDefault();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// --- Boot --------------------------------------------------------------------

splitText();
customCursor();
renderExamples();
loadVoices();
checkHealth().then(showHealthBanner);
route();
loadMarquee();
preload(!screen);
