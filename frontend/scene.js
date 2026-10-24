"use strict";

// Scroll-driven particle scene. Every element with [data-shape] is a keyframe:
// when it's centred in the viewport, the particles form that shape. Between
// keyframes each particle drifts from one shape to the next on its own schedule.
// Inside the app (not the landing page) shapes change over time instead, via
// Scene.show(shape). Scene.refresh() re-measures after layout changes.

(() => {
  const canvas = document.getElementById("scene");
  const gl = canvas.getContext("webgl", { antialias: false, alpha: false, premultipliedAlpha: false });
  const root = document.documentElement;
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (!gl) {
    window.Scene = { refresh() {}, show() {}, landing() {} };
    return;
  }

  const COUNT = innerWidth < 800 ? 18000 : 32000;
  const FADE = 0.35;      // fraction of a viewport over which shape labels fade

  let W = 0, H = 0, dpr = 1;
  let keyframes = [];     // { el, shape, scroll, hold }
  const buffers = {};     // shape name -> WebGLBuffer
  let smoothScroll = scrollY;
  const mouse = { x: 1e5, y: 1e5 };
  // App mode: time-based morph from `from` to `to`, started at `since`
  const app = { on: false, from: null, to: null, since: 0, builtAt: 0 };

  // --- Shapes (world units are CSS pixels, origin at viewport centre, y up) ---

  const rand = Math.random;
  const gauss = () => (rand() + rand() + rand() - 1.5) / 1.5;
  const portrait = () => H > W;

  function markShape(dx = 0, dy = 0, scale = 1) {
    const out = new Float32Array(COUNT * 3);
    const R = Math.min(H * 0.4, W * (portrait() ? 0.42 : 0.3)) * scale;
    for (let i = 0; i < COUNT; i++) {
      const pick = rand();
      let x, y, z = gauss() * R * 0.04;
      if (pick < 0.34) {            // ring
        const a = rand() * Math.PI * 2, r = R + gauss() * R * 0.025;
        x = Math.cos(a) * r; y = Math.sin(a) * r;
      } else if (pick < 0.7) {      // wave
        const u = rand() * 2 - 1;
        x = u * R * 0.8 + gauss() * R * 0.02;
        y = R * 0.45 * Math.sin(Math.PI * (u + 1)) + gauss() * R * 0.035;
        z *= 1.6;
      } else {                      // faint fill
        const a = rand() * Math.PI * 2, r = R * Math.sqrt(rand()) * 0.97;
        x = Math.cos(a) * r; y = Math.sin(a) * r;
      }
      out.set([x + dx, y + dy, z], i * 3);
    }
    return out;
  }

  function sphereShape() {
    const out = new Float32Array(COUNT * 3);
    const R = (portrait() ? 0.552 : 0.92) * H * 0.39;
    for (let i = 0; i < COUNT; i++) {
      const z = rand() * 2 - 1, a = rand() * Math.PI * 2;
      const r = R * (1 + gauss() * 0.012), s = Math.sqrt(1 - z * z);
      out.set([Math.cos(a) * s * r, z * r, Math.sin(a) * s * r], i * 3);
    }
    return out;
  }

  function treeShape() {
    const out = new Float32Array(COUNT * 3);
    const depth = 4;
    const Wt = portrait() ? W * 0.86 : W * 0.38;
    const Ht = H * (portrait() ? 0.42 : 0.6);
    const top = Ht / 2, cx = portrait() ? 0 : -W * 0.04;
    const nodes = [], edges = [];
    for (let l = 0; l < depth; l++) {
      const n = 2 ** l;
      for (let i = 0; i < n; i++) {
        const node = [cx + ((i + 0.5) / n - 0.5) * Wt, top - (l * Ht) / (depth - 1)];
        if (l > 0) edges.push([nodes[2 ** (l - 1) - 1 + (i >> 1)], node]);
        nodes.push(node);
      }
    }
    const r = Math.min(Ht * 0.045, Wt / 2 ** depth * 0.36);
    for (let i = 0; i < COUNT; i++) {
      let x, y;
      if (rand() < 0.5) {
        const [nx, ny] = nodes[(rand() * nodes.length) | 0];
        const a = rand() * Math.PI * 2;
        const d = rand() < 0.5 ? r * (1 + gauss() * 0.06) : r * Math.sqrt(rand());
        x = nx + Math.cos(a) * d; y = ny + Math.sin(a) * d;
      } else {
        const [[ax, ay], [bx, by]] = edges[(rand() * edges.length) | 0];
        const len = Math.hypot(bx - ax, by - ay);
        const t = r / len + rand() * (1 - (2 * r) / len), j = gauss() * 2.5;
        x = ax + (bx - ax) * t + ((by - ay) / len) * j;
        y = ay + (by - ay) * t - ((bx - ax) / len) * j;
      }
      out.set([x, y, gauss() * 8], i * 3);
    }
    return out;
  }

  // A twisted band following a centre curve; particles crowd its two edges.
  function ribbonShape(curve, width, turns) {
    const out = new Float32Array(COUNT * 3);
    for (let i = 0; i < COUNT; i++) {
      const u = rand();
      const [cx, cy] = curve(u);
      const theta = u * turns * Math.PI * 2;
      const w = width * (0.35 + 0.65 * Math.abs(Math.sin(u * Math.PI * 1.5 + 0.6)));
      const v = rand() < 0.55 ? Math.sign(rand() - 0.5) * (0.9 + rand() * 0.1) : rand() * 2 - 1;
      out.set([cx + gauss() * 2, cy + Math.cos(theta) * w * v, Math.sin(theta) * w * v * 2], i * 3);
    }
    return out;
  }

  const ribbon = () => ribbonShape(
    (u) => [(u - 0.5) * W * 1.3, (u - 0.5) * H * 0.55 + Math.sin(u * Math.PI * 3) * H * 0.09 - H * 0.05],
    H * 0.07, 1.6);

  const ribbonFlat = () => ribbonShape(
    (u) => [(u - 0.5) * W * 1.3, (u - 0.35) * H * 0.7 + Math.sin(u * Math.PI * 2.2 + 1) * H * 0.12],
    H * 0.05, 2.2);

  const ribbonLoops = () => ribbonShape((u) => {
    const t = u * Math.PI * 2 * 4.5, a = 1, b = 1.7;
    const span = Math.PI * 2 * 4.5 * a;
    const x = ((a * t - b * Math.sin(t)) / span - 0.5) * W * 1.25;
    return [x, -b * Math.cos(t) * H * 0.045 + u * H * 0.35 - H * 0.12];
  }, H * 0.03, 3);

  // A noisy band around an element, as it will sit when the page is scrolled to `atScroll`
  function frameShape(id, atScroll) {
    const out = new Float32Array(COUNT * 3);
    const box = document.getElementById(id);
    if (!box || atScroll == null) return out;
    const rect = box.getBoundingClientRect();
    const pad = H * 0.012, thick = H * 0.036;
    const w = rect.width + pad * 2, h = rect.height + pad * 2;
    const cx = rect.left + rect.width / 2 - W / 2;
    const cy = H / 2 - (rect.top + (scrollY - atScroll) + rect.height / 2);
    // Top and bottom bands run past the corners so the corners fill in
    const tw = w + thick * 2;
    const perim = 2 * (tw + h);
    for (let i = 0; i < COUNT; i++) {
      let p = rand() * perim, x, y;
      const d = thick * rand() + gauss() * 3;
      if (p < tw) { x = p - tw / 2; y = h / 2 + d; }
      else if ((p -= tw) < h) { x = w / 2 + d; y = h / 2 - p; }
      else if ((p -= h) < tw) { x = tw / 2 - p; y = -h / 2 - d; }
      else { p -= tw; x = -w / 2 - d; y = -h / 2 + p; }
      out.set([cx + x, cy + y, gauss() * 10], i * 3);
    }
    return out;
  }

  // A faint haze across the screen; most particles leave through the bottom
  function dustShape() {
    const out = new Float32Array(COUNT * 3);
    for (let i = 0; i < COUNT; i++) {
      const away = rand() < 0.8;
      out.set([
        (rand() - 0.5) * W * 1.1,
        away ? -H * (0.8 + rand()) : (rand() - 0.5) * H * 1.1,
        (rand() - 0.5) * 300,
      ], i * 3);
    }
    return out;
  }

  const SHAPES = {
    mark: () => markShape(),
    markRight: () => (portrait() ? markShape(0, -H * 0.3, 0.65) : markShape(W * 0.24, H * 0.04, 1.1)),
    sphere: sphereShape,
    tree: treeShape,
    ribbon, ribbonFlat, ribbonLoops,
    frame: () => frameShape("landing-frame", keyframes.find((k) => k.shape === "frame")?.scroll),
    panel: () => { app.builtAt = scrollY; return frameShape("frame-box", scrollY); },
    dust: dustShape,
  };

  // Gentle per-shape rotation about the vertical axis, in radians
  const ROTATION = {
    mark: (t) => Math.sin(t * 0.4) * 0.22,
    markRight: (t) => Math.sin(t * 0.4) * 0.22,
    sphere: (t) => t * 0.18,
  };

  // --- GL setup ---------------------------------------------------------------

  const VERT = `
    attribute vec3 aA;
    attribute vec3 aB;
    attribute vec4 aRand;
    uniform float uMix, uTime, uRotA, uRotB, uDpr, uMotion, uShift;
    uniform vec2 uRes, uMouse;
    varying float vAlpha;

    vec3 rotY(vec3 p, float a) {
      float c = cos(a), s = sin(a);
      return vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
    }

    void main() {
      float t = clamp((uMix - aRand.x * 0.45) / 0.55, 0.0, 1.0);
      t = t * t * (3.0 - 2.0 * t);
      vec3 p = mix(rotY(aA, uRotA), rotY(aB, uRotB), t);
      p.y += uShift;

      // scatter mid-flight, so shapes dissolve rather than slide
      float ang = aRand.z * 6.2832;
      vec3 dir = vec3(cos(ang), sin(ang), aRand.w - 0.5);
      p += dir * sin(3.1416 * t) * (40.0 + 160.0 * aRand.w) * uMotion;

      p.xy += vec2(sin(uTime * 0.7 + aRand.z * 40.0), cos(uTime * 0.6 + aRand.w * 31.0)) * 1.4 * uMotion;

      float persp = 1400.0 / (1400.0 - p.z);
      vec2 xy = p.xy * persp;

      vec2 d = xy - uMouse;
      float dist = length(d);
      if (dist > 0.001) xy += d / dist * max(0.0, 90.0 - dist) * 0.55;

      gl_Position = vec4(xy / (uRes * 0.5), 0.0, 1.0);
      gl_PointSize = (0.9 + aRand.y * 1.5) * uDpr * persp;
      vAlpha = (0.3 + 0.5 * aRand.y) * clamp(0.65 + p.z / 700.0, 0.25, 1.0);
    }`;

  const FRAG = `
    precision mediump float;
    varying float vAlpha;
    void main() {
      float r = length(gl_PointCoord - 0.5);
      if (r > 0.5) discard;
      gl_FragColor = vec4(0.941, 0.949, 0.941, vAlpha * (1.0 - r * 1.4));
    }`;

  function compile(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }

  const prog = gl.createProgram();
  gl.attachShader(prog, compile(gl.VERTEX_SHADER, VERT));
  gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FRAG));
  gl.linkProgram(prog);
  gl.useProgram(prog);

  const loc = {};
  for (const n of ["aA", "aB", "aRand"]) loc[n] = gl.getAttribLocation(prog, n);
  for (const n of ["uMix", "uTime", "uRotA", "uRotB", "uDpr", "uMotion", "uShift", "uRes", "uMouse"]) loc[n] = gl.getUniformLocation(prog, n);

  const randData = new Float32Array(COUNT * 4);
  for (let i = 0; i < randData.length; i++) randData[i] = rand();
  const randBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, randBuf);
  gl.bufferData(gl.ARRAY_BUFFER, randData, gl.STATIC_DRAW);
  gl.enableVertexAttribArray(loc.aRand);
  gl.vertexAttribPointer(loc.aRand, 4, gl.FLOAT, false, 0, 0);
  gl.enableVertexAttribArray(loc.aA);
  gl.enableVertexAttribArray(loc.aB);

  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
  gl.clearColor(0x22 / 255, 0x21 / 255, 0x24 / 255, 1);

  function upload(name) {
    if (!buffers[name]) buffers[name] = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffers[name]);
    gl.bufferData(gl.ARRAY_BUFFER, SHAPES[name](), gl.STATIC_DRAW);
  }

  // --- Layout -----------------------------------------------------------------

  function measureKeyframes() {
    const max = document.documentElement.scrollHeight - innerHeight;
    keyframes = [...document.querySelectorAll("[data-shape]")]
      .filter((el) => SHAPES[el.dataset.shape])
      .map((el) => {
        const r = el.getBoundingClientRect();
        const centre = r.top + scrollY + r.height / 2 - innerHeight / 2;
        return {
          el, shape: el.dataset.shape,
          scroll: Math.max(0, Math.min(max, centre)),
          hold: parseFloat(el.dataset.hold || "0") * innerHeight,
        };
      })
      .sort((a, b) => a.scroll - b.scroll);
  }

  function resize() {
    dpr = Math.min(devicePixelRatio || 1, 2);
    W = innerWidth; H = innerHeight;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    gl.viewport(0, 0, canvas.width, canvas.height);
    if (app.on) {
      for (const name of new Set([app.from, app.to])) upload(name);
    } else {
      measureKeyframes();
      for (const name of new Set(keyframes.map((k) => k.shape))) upload(name);
    }
  }

  function refresh() {
    if (app.on) {
      if (app.to === "panel") upload("panel");
      return;
    }
    measureKeyframes();
    if (buffers.frame) upload("frame");
  }

  // Enter app mode (or change shape within it)
  function show(shape) {
    const wasOn = app.on;
    app.on = true;
    if (shape === app.to && wasOn) {
      if (shape === "panel") upload("panel");
      return;
    }
    app.from = app.to || current.shape || "dust";
    app.to = shape;
    app.since = performance.now();
    upload(app.to);
    if (!buffers[app.from]) upload(app.from);
  }

  // Back to the scroll-driven landing page
  function landing() {
    app.on = false;
    app.to = null;
    requestAnimationFrame(() => {
      measureKeyframes();
      for (const name of new Set(keyframes.map((k) => k.shape))) if (!buffers[name] || name === "frame") upload(name);
    });
  }

  // --- Frame loop ---------------------------------------------------------------

  function bindShape(attr, name) {
    gl.bindBuffer(gl.ARRAY_BUFFER, buffers[name]);
    gl.vertexAttribPointer(attr, 3, gl.FLOAT, false, 0, 0);
  }

  const current = { shape: null };   // the shape most recently on screen

  function frame(now) {
    const t = reduceMotion ? 0 : now / 1000;
    smoothScroll += (scrollY - smoothScroll) * (reduceMotion ? 1 : 0.09);
    if (app.on) {
      const mix = reduceMotion ? 1 : Math.min(1, (now - app.since) / 1800);
      current.shape = mix > 0.5 ? app.to : app.from;
      const shift = app.to === "panel" ? scrollY - app.builtAt : 0;
      draw({ shape: app.from }, { shape: app.to }, mix, t, shift);
      requestAnimationFrame(frame);
      return;
    }
    const s = smoothScroll;

    // Which pair of keyframes are we between?
    let a = keyframes[0], b = keyframes[0], mix = 0;
    for (let i = 0; i < keyframes.length - 1; i++) {
      const k0 = keyframes[i], k1 = keyframes[i + 1];
      if (s >= k0.scroll || i === 0) { a = k0; b = k1; }
    }
    if (a && b && a !== b) {
      const start = a.scroll + a.hold, end = b.scroll - b.hold;
      mix = end > start ? Math.max(0, Math.min(1, (s - start) / (end - start))) : s >= end ? 1 : 0;
    }

    // Readiness per shape, for labels tied to a shape (--w-sphere etc.)
    const weights = {};
    for (const k of keyframes) {
      const w = Math.max(0, Math.min(1, 1 - (Math.abs(s - k.scroll) - k.hold) / (FADE * H)));
      weights[k.shape] = Math.max(weights[k.shape] || 0, w);
    }
    for (const [name, w] of Object.entries(weights)) root.style.setProperty(`--w-${name}`, w.toFixed(3));

    if (a) current.shape = mix > 0.5 ? b.shape : a.shape;
    draw(a, b, mix, t, 0);
    requestAnimationFrame(frame);
  }

  function draw(a, b, mix, t, shift) {
    gl.clear(gl.COLOR_BUFFER_BIT);
    if (a && buffers[a.shape] && buffers[b.shape]) {
      bindShape(loc.aA, a.shape);
      bindShape(loc.aB, b.shape);
      gl.uniform1f(loc.uMix, mix);
      gl.uniform1f(loc.uTime, t);
      gl.uniform1f(loc.uRotA, (ROTATION[a.shape] || (() => 0))(t));
      gl.uniform1f(loc.uRotB, (ROTATION[b.shape] || (() => 0))(t));
      gl.uniform1f(loc.uDpr, dpr);
      gl.uniform1f(loc.uMotion, reduceMotion ? 0 : 1);
      gl.uniform1f(loc.uShift, shift);
      gl.uniform2f(loc.uRes, W, H);
      gl.uniform2f(loc.uMouse, mouse.x, mouse.y);
      gl.drawArrays(gl.POINTS, 0, COUNT);
    }
  }

  addEventListener("resize", resize);
  addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse") return;
    mouse.x = e.clientX - W / 2;
    mouse.y = H / 2 - e.clientY;
  });
  document.addEventListener("pointerleave", () => { mouse.x = mouse.y = 1e5; });

  resize();
  const ro = new ResizeObserver(refresh);
  ro.observe(document.body);
  ro.observe(document.getElementById("frame-box"));
  ro.observe(document.getElementById("landing-frame"));
  requestAnimationFrame(frame);

  window.Scene = { refresh, show, landing };
})();
