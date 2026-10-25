import { ConvexCredentials } from "@convex-dev/auth/providers/ConvexCredentials";
import { Password } from "@convex-dev/auth/providers/Password";
import { convexAuth, retrieveAccount } from "@convex-dev/auth/server";
import { ConvexError } from "convex/values";
import { internal } from "./_generated/api";
import { createOrUpdateUser, normalizeUsername, usernameProblem } from "./users";

const WRONG_LOGIN = "Wrong username, email or password";
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const { auth, signIn, signOut, store, isAuthenticated } = convexAuth({
  providers: [
    // Creates accounts (flow "signUp"): username + email + password.
    Password({
      profile(params) {
        const email = String(params.email ?? "").trim().toLowerCase();
        if (!EMAIL_RE.test(email)) throw new ConvexError("Enter a valid email address");
        const username = String(params.username ?? "").trim();
        const problem = usernameProblem(normalizeUsername(username));
        if (problem) throw new ConvexError(problem);
        return { email, username, usernameLower: normalizeUsername(username) };
      },
      validatePasswordRequirements(password) {
        if (!password || password.length < 8) throw new ConvexError("Passwords need at least 8 characters");
      },
    }),
    // Signs in with a username or an email. The username is resolved to its account
    // here on the server, so the sign-in form can't be used to look up emails.
    ConvexCredentials({
      id: "login",
      authorize: async (credentials, ctx) => {
        const identifier = String(credentials.identifier ?? "");
        const password = String(credentials.password ?? "");
        if (!identifier || !password) throw new ConvexError(WRONG_LOGIN);
        const found = await ctx.runQuery(internal.users.findForLogin, { identifier });
        if (!found) throw new ConvexError(WRONG_LOGIN);
        try {
          const { user } = await retrieveAccount(ctx, {
            provider: "password",
            account: { id: found.email, secret: password },
          });
          return { userId: user._id };
        } catch {
          throw new ConvexError(WRONG_LOGIN);
        }
      },
    }),
  ],
  callbacks: {
    createOrUpdateUser: (ctx, args) => createOrUpdateUser(ctx as never, args as never),
  },
});
