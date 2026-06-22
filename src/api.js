const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function getRecommendations(payload) {
  const res = await fetch(`${BASE}/api/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),  // send as-is, already lowercase
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`${res.status}: ${err}`);
  }
  return res.json();
}