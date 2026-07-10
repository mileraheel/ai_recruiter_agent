import { createContext, useContext, useState, useCallback } from "react";
import { api, getToken, getRole, setToken, setRole, clearToken, decodeJwtRole } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [isAuthed, setIsAuthed] = useState(!!getToken());
  const [role, setRoleState] = useState(getRole());
  const [error, setError] = useState(null);

  // The single unified login (see Login.jsx) -- role isn't known ahead
  // of time the way loginAdmin/loginCandidate/etc. below know theirs,
  // so it's decoded from the returned token, same as loginWithToken's
  // invite-redemption case.
  const login = useCallback(async (identifier, password) => {
    setError(null);
    try {
      const res = await api.signin(identifier, password);
      const resolvedRole = decodeJwtRole(res.access_token);
      setToken(res.access_token);
      setRole(resolvedRole);
      setRoleState(resolvedRole);
      setIsAuthed(true);
      return resolvedRole;
    } catch (e) {
      setError(e.detail || "Login failed");
      return null;
    }
  }, []);

  const loginAdmin = useCallback(async (username, password) => {
    setError(null);
    try {
      const res = await api.login(username, password);
      setToken(res.access_token);
      setRole("admin");
      setRoleState("admin");
      setIsAuthed(true);
      return true;
    } catch (e) {
      setError(e.detail || "Login failed");
      return false;
    }
  }, []);

  const loginSuperuser = useCallback(async (username, password) => {
    setError(null);
    try {
      const res = await api.superuserLogin(username, password);
      setToken(res.access_token);
      setRole("superuser");
      setRoleState("superuser");
      setIsAuthed(true);
      return true;
    } catch (e) {
      setError(e.detail || "Login failed");
      return false;
    }
  }, []);

  const loginStaff = useCallback(async (username, password) => {
    setError(null);
    try {
      const res = await api.staffLogin(username, password);
      setToken(res.access_token);
      setRole("staff");
      setRoleState("staff");
      setIsAuthed(true);
      return true;
    } catch (e) {
      setError(e.detail || "Login failed");
      return false;
    }
  }, []);

  // For flows that receive a token/role from somewhere other than a
  // role-specific login call -- currently just invite redemption (see
  // AcceptInvite.jsx), which doesn't know the role ahead of time the
  // way loginAdmin/loginCandidate/etc. do.
  const loginWithToken = useCallback((token, role) => {
    setToken(token);
    setRole(role);
    setRoleState(role);
    setIsAuthed(true);
  }, []);

  const loginCandidate = useCallback(async (loginEmail, password) => {
    setError(null);
    try {
      const res = await api.candidateLogin(loginEmail, password);
      setToken(res.access_token);
      setRole("candidate");
      setRoleState("candidate");
      setIsAuthed(true);
      return true;
    } catch (e) {
      setError(e.detail || "Login failed");
      return false;
    }
  }, []);

  const signupCandidate = useCallback(async (fullName, organizationName, loginEmail, password) => {
    setError(null);
    try {
      const res = await api.candidateSignup({
        full_name: fullName,
        organization_name: organizationName,
        login_email: loginEmail,
        password,
      });
      setToken(res.access_token);
      setRole("candidate");
      setRoleState("candidate");
      setIsAuthed(true);
      return true;
    } catch (e) {
      setError(e.detail || "Sign up failed");
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setIsAuthed(false);
    setRoleState(null);
    sessionStorage.removeItem("ai_recruiter_trial_banner_shown");
  }, []);

  return (
    <AuthContext.Provider
      value={{
        isAuthed, role, login, loginAdmin, loginCandidate, loginSuperuser, loginStaff, loginWithToken,
        signupCandidate, logout, error,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
