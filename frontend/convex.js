"use strict";

// The connection to Convex (loaded from unpkg as the global `convex`), plus sessions.
//
//   call(kind, "videos:feed", args)        one-off query, mutation or action
//   watch("videos:get", args, onUpdate)    live query; returns an unsubscribe function
//   signUp / signInWith / signOutNow       accounts (Convex Auth)
//   currentUser, onAuthChange(fn)          who's signed in
//
// Sessions are a short-lived token plus a refresh token, kept in localStorage.

const TOKEN_KEY = "animai-token";
const REFRESH_KEY = "animai-refresh-token";

let convexClient = null;   // live client: queries, mutations, subscriptions
let convexHttp = null;     // plain client for sign-in and token refresh (never waits on auth)
let currentUser = null;    // { _id, username, email } or null
const authListeners = new Set();

function readStore(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function writeStore(key, value) {
  try {
    if (value) localStorage.setItem(key, value); else localStorage.removeItem(key);
  } catch { /* storage blocked: the session lasts until reload */ }
}

const convexReady = (async () => {
  const cfg = await (await fetch("/api/config")).json();
  convexClient = new convex.ConvexClient(cfg.convexUrl);
  convexHttp = new convex.ConvexHttpClient(cfg.convexUrl);
  if (readStore(REFRESH_KEY)) startSession();
  else await refreshUser();
})();

function fnRef(name) {
  const [module, fn] = name.split(":");
  return convex.anyApi[module][fn];
}

// Convex errors carry our message in `data`; anything else gets a plain fallback
function friendlyError(err) {
  const data = err?.data;
  if (typeof data === "string") return new Error(data);
  if (data && typeof data.message === "string") return new Error(data.message);
  if (/already exists/i.test(err?.message || "")) return new Error("An account with that email already exists");
  return new Error("Something went wrong. Try again.");
}

async function call(kind, name, args = {}) {
  await convexReady;
  try {
    return await convexClient[kind](fnRef(name), args);
  } catch (err) {
    throw friendlyError(err);
  }
}

function watch(name, args, onUpdate, onError) {
  let unsubscribe = null;
  let stopped = false;
  convexReady.then(() => {
    if (stopped) return;
    unsubscribe = convexClient.onUpdate(fnRef(name), args, onUpdate, (err) => onError?.(friendlyError(err)));
  });
  return () => {
    stopped = true;
    unsubscribe?.();
  };
}

// --- Sessions ----------------------------------------------------------------

function storeTokens(tokens) {
  writeStore(TOKEN_KEY, tokens?.token);
  writeStore(REFRESH_KEY, tokens?.refreshToken);
}

let refreshing = null;
function refreshSession() {
  refreshing ??= (async () => {
    const refreshToken = readStore(REFRESH_KEY);
    if (!refreshToken) return null;
    try {
      const result = await convexHttp.action(fnRef("auth:signIn"), { refreshToken });
      if (result?.tokens) {
        storeTokens(result.tokens);
        return result.tokens.token;
      }
    } catch { /* expired or revoked */ }
    storeTokens(null);
    return null;
  })().finally(() => { refreshing = null; });
  return refreshing;
}

async function fetchToken({ forceRefreshToken }) {
  if (!forceRefreshToken) {
    const token = readStore(TOKEN_KEY);
    if (token) return token;
  }
  return await refreshSession();
}

function startSession() {
  convexClient.setAuth(fetchToken, () => refreshUser());
}

async function refreshUser() {
  try {
    currentUser = await convexClient.query(fnRef("users:me"), {});
  } catch {
    currentUser = null;
  }
  authListeners.forEach((fn) => fn(currentUser));
}

function onAuthChange(fn) {
  authListeners.add(fn);
  return () => authListeners.delete(fn);
}

async function finishSignIn(result) {
  if (!result?.tokens) throw new Error("Something went wrong. Try again.");
  storeTokens(result.tokens);
  startSession();
  await refreshUser();
  return currentUser;
}

async function signUp({ username, email, password }) {
  await convexReady;
  try {
    return await finishSignIn(await convexHttp.action(fnRef("auth:signIn"), {
      provider: "password",
      params: { flow: "signUp", username, email, password },
    }));
  } catch (err) {
    throw err.message?.startsWith("Something") ? err : friendlyError(err);
  }
}

async function signInWith({ identifier, password }) {
  await convexReady;
  try {
    return await finishSignIn(await convexHttp.action(fnRef("auth:signIn"), {
      provider: "login",
      params: { identifier, password },
    }));
  } catch (err) {
    throw err.message?.startsWith("Something") ? err : friendlyError(err);
  }
}

async function signOutNow() {
  await convexReady;
  try { await convexClient.action(fnRef("auth:signOut"), {}); } catch { /* already signed out */ }
  storeTokens(null);
  convexClient.client.clearAuth();  // the browser ConvexClient wraps the connection that holds auth
  currentUser = null;
  authListeners.forEach((fn) => fn(null));
}
