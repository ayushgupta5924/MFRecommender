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

// A guest's portfolio review, kept only for this browser tab (gone when the tab closes).
export const GUEST_REVIEW_KEY = "mfa:guestReview";

export function loadSession(key, fallback) {
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw == null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export function saveSession(key, value) {
  try {
    if (value === undefined) window.sessionStorage.removeItem(key);
    else window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch { /* storage full or blocked: the review still shows, it just won't survive a refresh */ }
}

// Removes questionnaire answers, the last plan, a guest review and any half-finished login from this browser.
export function clearPlanData() {
  for (const store of ["localStorage", "sessionStorage"]) {
    try {
      Object.keys(window[store])
        .filter((k) => k.startsWith("mfa:"))
        .forEach((k) => window[store].removeItem(k));
    } catch { /* storage blocked: nothing was saved anyway */ }
  }
}

// useState that is restored after a page refresh.
export function usePersistentState(key, initial) {
  const [value, setValue] = useState(() => load(key, initial));
  useEffect(() => { save(key, value); }, [key, value]);
  return [value, setValue];
}
