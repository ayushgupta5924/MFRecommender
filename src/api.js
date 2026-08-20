const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, payload) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`${res.status}: ${err}`);
  }
  return res.json();
}

// New portfolio endpoint — returns named portfolio with SIP math
export function getPortfolio(payload) {
  return request("/api/portfolio", payload);
}

// Legacy endpoint — flat fund list
export function getRecommendations(payload) {
  return request("/api/recommend", payload);
}