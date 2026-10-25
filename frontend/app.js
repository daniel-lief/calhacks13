"use strict";

// Routing between the landing story and the app screens.
//
//   #/            landing (scroll story)      #/watch[/id]  vertical scroller
//   #/discover    public video grid           #/video/<id>  one video, 16:9 watch page
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
  if (h.startsWith("#/discover") || h.startsWith("#/feed")) return { screen: "feed" };
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
      window.Scene.refresh();
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

  // Keep the decorative background in sync with the active screen.
  requestAnimationFrame(() => window.Scene.show(SCENE_SHAPE[screen]));
}
window.addEventListener("hashchange", route);

$("#monogram").addEventListener("click", (e) => {
  e.preventDefault();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// --- Boot --------------------------------------------------------------------

splitText();
customCursor();
renderExamples();
loadVoices();
loadThemes();
checkHealth().then(showHealthBanner);
route();
