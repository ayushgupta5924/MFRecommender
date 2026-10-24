const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// The free backend sleeps when idle and can take ~30-60s to wake up.
const TIMEOUT_MS = 90_000;

async function request(path, payload) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: payload ? "POST" : "GET",
      headers: payload ? { "Content-Type": "application/json" } : undefined,
      body: payload ? JSON.stringify(payload) : undefined,
      signal: controller.signal,
    });
    if (!res.ok) {
      let message = `Request failed (${res.status})`;
      try {
        const body = await res.json();
        if (typeof body.detail === "string") message = body.detail;
        else if (Array.isArray(body.detail)) message = body.detail.map((d) => d.msg).join("; ");
      } catch { /* non-JSON error body */ }
      throw new Error(message);
    }
    return res.json();
  } catch (e) {
    if (e.name === "AbortError") throw new Error("The server took too long to respond. Please try again.", { cause: e });
    if (e instanceof TypeError) throw new Error("Could not reach the server. Check your connection and try again.", { cause: e });
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// Named portfolio with fund picks, projections and evidence
export function getPortfolio(payload) {
  return request("/api/portfolio", payload);
}

// Fire-and-forget ping so the backend is awake by the time the form is submitted.
export function warmUp() {
  request("/api/health").catch(() => {});
}
