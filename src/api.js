// All calls go to /api on this site: Vercel forwards them to the backend (vercel.json) and the
// Vite dev server does the same locally. Same-site requests let the login cookie work in every browser.

// The free backend sleeps when idle and can take ~30-60s to wake up.
const TIMEOUT_MS = 90_000;

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method, json, form } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(path, {
      method: method || (json || form ? "POST" : "GET"),
      headers: json ? { "Content-Type": "application/json" } : undefined,
      body: json ? JSON.stringify(json) : form,
      credentials: "same-origin",
      signal: controller.signal,
    });
    if (!res.ok) {
      let message = `Request failed (${res.status})`;
      try {
        const body = await res.json();
        if (typeof body.detail === "string") message = body.detail;
        else if (Array.isArray(body.detail)) message = body.detail.map((d) => d.msg).join("; ");
      } catch { /* non-JSON error body */ }
      throw new ApiError(message, res.status);
    }
    return res.json();
  } catch (e) {
    if (e.name === "AbortError") throw new ApiError("The server took too long to respond. Please try again.", 0);
    if (e instanceof TypeError) throw new ApiError("Could not reach the server. Check your connection and try again.", 0);
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// ── Plans ──
export const getPortfolio = (payload) => request("/api/portfolio", { json: payload });

// Also wakes the backend while the visitor reads the intro, so the plan comes back quickly.
export const getHealth = () => request("/api/health");

// ── Auth ──
export const startSignup = (fullName, email, consent) =>
  request("/api/auth/signup/start", { json: { full_name: fullName, email, consent } });
export const startLogin = (email) => request("/api/auth/login/start", { json: { email } });
export const verifyCode = (email, code, purpose, consent = false) =>
  request("/api/auth/verify", { json: { email, code, purpose, consent } });
export const getMe = () => request("/api/auth/me");
export const logout = () => request("/api/auth/logout", { method: "POST" });
export const deleteAccount = () => request("/api/account", { method: "DELETE" });
export const setAlerts = (enabled) => request("/api/account/alerts", { method: "PUT", json: { enabled } });

// ── Portfolio review ──
export const getReview = () => request("/api/review");
export const deleteReview = () => request("/api/review", { method: "DELETE" });
export const removeHolding = (id) => request(`/api/review/holdings/${encodeURIComponent(id)}`, { method: "DELETE" });
export const addHolding = (holding) => request("/api/review/holdings", { json: holding });
export const searchFunds = (q) => request(`/api/funds/search?q=${encodeURIComponent(q)}`);

export function uploadStatement(file, password, consent, alerts) {
  const form = new FormData();
  form.append("file", file);
  form.append("password", password);
  form.append("consent", consent ? "true" : "false");
  form.append("alerts", alerts ? "true" : "false");
  return request("/api/review/upload", { form });
}

// ── Portfolio review without an account: the browser keeps the holdings and sends them back ──
export const guestReview = (holdings, add) => request("/api/review/guest", { json: { consent: true, holdings, add } });

export function guestUpload(file, password, consent) {
  const form = new FormData();
  form.append("file", file);
  form.append("password", password);
  form.append("consent", consent ? "true" : "false");
  return request("/api/review/guest/upload", { form });
}

// ── Saved plans ──
export const listPlans = () => request("/api/plans");
export const getPlan = (id) => request(`/api/plans/${id}`);
export const savePlan = (profile, result, name) => request("/api/plans", { json: { profile, result, name } });
export const deletePlan = (id) => request(`/api/plans/${id}`, { method: "DELETE" });
