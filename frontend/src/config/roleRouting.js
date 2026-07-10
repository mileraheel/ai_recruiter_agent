// Single source of truth for "what does this role see right after
// logging in" -- shared by Login.jsx (unified sign-in), ResetPassword.jsx
// (reset then log straight in), and AcceptInvite.jsx (redeem then log
// straight in), so the three places a session can start all agree on
// where each role lands.
export const ROLE_LANDING = {
  admin: "/post-job",
  candidate: "/candidate/profile",
  staff: "/staff/dashboard",
  superuser: "/superuser/dashboard",
};

// There's only one login page now -- kept as a named constant (rather
// than the string literal "/login" scattered around) so intent is
// clear at each call site.
export const LOGIN_PATH = "/login";
