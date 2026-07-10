// Single source of truth for the platform's display name in the UI.
// Sourced from VITE_APP_NAME (see .env / .env.example) so it can change
// without touching component code. Falls back to "Role Pace" if unset.
export const APP_NAME = import.meta.env.VITE_APP_NAME || "Role Pace";
