import { createContext, useContext, useState, useCallback } from "react";
import { api, getToken, getRole, setToken, setRole, clearToken } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [isAuthed, setIsAuthed] = useState(!!getToken());
  const [role, setRoleState] = useState(getRole());
  const [error, setError] = useState(null);

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
    <AuthContext.Provider value={{ isAuthed, role, loginAdmin, loginCandidate, loginSuperuser, loginStaff, signupCandidate, logout, error }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
