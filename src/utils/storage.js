import { useEffect, useState } from "react";

// The most recent plan: the answers sent, the plan returned, and its id once saved to the account.
export const LAST_PLAN_KEY = "mfa:lastPlan";

// Per-browser storage that survives a refresh. Storage can be unavailable (private
// windows, blocked site data), so every access is wrapped and falls back gracefully.

export function load(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw == null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export function save(key, value) {
  try {
    if (value === undefined) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, JSON.stringify(value));
  } catch { /* storage full or blocked: the app still works, it just won't remember */ }
}

// useState that is restored after a page refresh.
export function usePersistentState(key, initial) {
  const [value, setValue] = useState(() => load(key, initial));
  useEffect(() => { save(key, value); }, [key, value]);
  return [value, setValue];
}
