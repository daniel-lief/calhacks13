"use strict";

// The canvas surrounds the hero copy with a color orbit and scattered particles.
// The richer lesson illustrations live alongside their story copy.
(() => {
  const canvas = document.getElementById("scene");
  const ctx = canvas.getContext("2d");
  if (!ctx) { window.Scene = { refresh() {}, show() {}, landing() {} }; return; }
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  const colors = ["#ECD288", "#F0B3BC", "#A6C7EA", "#F1C29D", "#C7B6ED", "#AAD9B0"];
  let W = 0, H = 0, appMode = false, raf = 0, entranceStart = null;
  const clamp = n => Math.max(0, Math.min(1, n));
  const random = n => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
  const dots = Array.from({length: 78}, (_, i) => ({
    x: random(i * 3), y: random(i * 3 + 1), r: 1.6 + random(i * 3 + 2) * 3.2,
    color: colors[i % colors.length], phase: i * .71,
  }));
  function requestDraw() { if (!raf && !document.hidden) raf = requestAnimationFrame(frame); }
  function bubble(x, y, r, fill) {
    ctx.fillStyle = fill; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  }
  function resize() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    W = innerWidth; H = innerHeight;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    requestDraw();
  }
  function orbit(t, bounds, entrance) {
    const cx = bounds.left + bounds.width / 2, cy = bounds.top + bounds.height / 2;
    const r = Math.min(H * .51, W * .40);
    const ry = Math.min(H * .36, Math.max(r * .81, 180));
    const p = entrance - 1;
    const scale = .7 + .3 * (1 + 2.70158 * p * p * p + 1.70158 * p * p);
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(-Math.PI / 7);
    ctx.scale(scale, scale); ctx.globalAlpha *= Math.min(1, entrance * 3);
    ctx.strokeStyle = "#e8d9d1"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.ellipse(0, 0, r, ry, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.save(); ctx.setLineDash([3, 8]); ctx.strokeStyle = "#eadfd9";
    ctx.beginPath(); ctx.ellipse(0, 0, r * 1.12, ry * 1.15, 0, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
    for (let i = 0; i < 6; i++) {
      const a = i * Math.PI / 3 + t * .075;
      const x = Math.cos(a) * r, y = Math.sin(a) * ry;
      bubble(x, y + Math.sin(t * .65 + i) * ry * .016, r * (.075 + i % 3 * .012), colors[i]);
    }
    bubble(r * 1.25, -r * .62, r * .034, "#ef7d99");
    bubble(-r * 1.16, r * .53, r * .045, "#e8edcc");
    ctx.restore();
  }
  function frame(now) {
    raf = 0; ctx.clearRect(0, 0, W, H);
    const t = motion.matches ? 0 : now / 1000;
    if (appMode) {
      ctx.save(); ctx.globalAlpha = .22;
      bubble(W + 32, H - 20, 110, "#f1c29d"); bubble(W - 70, 27, 24, "#e8edcc");
      ctx.restore();
    } else {
      ctx.save(); ctx.globalAlpha = .52;
      for (const d of dots) bubble(d.x * W + Math.sin(t * .15 + d.phase) * 4,
        d.y * H + Math.cos(t * .2 + d.phase) * 5, d.r, d.color);
      ctx.restore();
      const hero = document.querySelector(".hero");
      const bounds = hero?.getBoundingClientRect();
      const visibility = bounds ? clamp(1 - Math.abs(bounds.top) / H) : 0;
      if (visibility) {
        entranceStart ??= now;
        const entrance = motion.matches ? 1 : clamp((now - entranceStart) / 1100);
        ctx.save(); ctx.globalAlpha = visibility; orbit(t, bounds, entrance); ctx.restore();
      }
    }
    if (!motion.matches && !document.hidden && !appMode) requestDraw();
  }
  window.Scene = {
    refresh: requestDraw,
    show() { appMode = true; requestDraw(); },
    landing() { appMode = false; entranceStart = null; requestDraw(); },
  };
  addEventListener("resize", resize);
  addEventListener("scroll", requestDraw, {passive: true});
  motion.addEventListener("change", requestDraw);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) { cancelAnimationFrame(raf); raf = 0; } else requestDraw();
  });
  resize();
})();
