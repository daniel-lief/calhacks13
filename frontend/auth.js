"use strict";

// Sign-in / create-account panel and the sidebar account area.
// requireSignIn() is what Like, Save and Create call before doing anything.

const au = {
  panel: document.getElementById("auth-panel"),
  reason: document.getElementById("auth-reason"),
  tabs: document.querySelectorAll("#auth-panel [data-auth-tab]"),
  signIn: document.getElementById("signin-form"),
  signUp: document.getElementById("signup-form"),
  close: document.getElementById("auth-close"),
  account: document.getElementById("account"),
};

function showAuthTab(name) {
  au.tabs.forEach((t) => {
    const on = t.dataset.authTab === name;
    t.classList.toggle("on", on);
    t.setAttribute("aria-selected", String(on));
  });
  au.signIn.hidden = name !== "signin";
  au.signUp.hidden = name !== "signup";
  (name === "signin" ? au.signIn : au.signUp).querySelector("input")?.focus();
}

function openAuth(reason = "", tab = "signin") {
  au.reason.textContent = reason;
  au.reason.hidden = !reason;
  au.panel.hidden = false;
  [au.signIn, au.signUp].forEach((f) => { f.reset(); f.querySelector(".auth-error").textContent = ""; });
  showAuthTab(tab);
}

function closeAuth() {
  au.panel.hidden = true;
}

/** True if signed in; otherwise opens the sign-in panel and returns false. */
function requireSignIn(reason = "Sign in to continue") {
  if (currentUser) return true;
  openAuth(reason);
  return false;
}

async function submitAuth(form, action) {
  const error = form.querySelector(".auth-error");
  const button = form.querySelector("button[type=submit]");
  error.textContent = "";
  button.disabled = true;
  try {
    await action(Object.fromEntries(new FormData(form)));
    closeAuth();
  } catch (err) {
    error.textContent = err.message;
  } finally {
    button.disabled = false;
  }
}

au.signIn.addEventListener("submit", (e) => {
  e.preventDefault();
  submitAuth(au.signIn, ({ identifier, password }) => signInWith({ identifier: identifier.trim(), password }));
});
au.signUp.addEventListener("submit", (e) => {
  e.preventDefault();
  submitAuth(au.signUp, ({ username, email, password }) =>
    signUp({ username: username.trim(), email: email.trim(), password }));
});
au.tabs.forEach((t) => t.addEventListener("click", () => showAuthTab(t.dataset.authTab)));
au.close.addEventListener("click", closeAuth);
au.panel.addEventListener("click", (e) => { if (e.target === au.panel) closeAuth(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !au.panel.hidden) closeAuth(); });

// --- Sidebar account area ------------------------------------------------------

function renderAccount(user) {
  au.account.replaceChildren();
  if (user) {
    const name = document.createElement("span");
    name.className = "t-20 account-name";
    name.textContent = `@${user.username}`;
    const out = document.createElement("button");
    out.type = "button";
    out.className = "link-button muted caps t-16";
    out.textContent = "Sign out";
    out.addEventListener("click", () => signOutNow());
    au.account.append(name, out);
  } else {
    const inBtn = document.createElement("button");
    inBtn.type = "button";
    inBtn.className = "link-button t-20";
    inBtn.textContent = "Sign in";
    inBtn.addEventListener("click", () => openAuth());
    au.account.append(inBtn);
  }
}

onAuthChange(renderAccount);
renderAccount(null);
