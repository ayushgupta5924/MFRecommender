export function getCategoryColor(risk) {
  const r = (risk || "").toLowerCase();
  if (r === "very high") return "#8e0000";
  if (r === "high") return "#c62828";
  if (r === "moderate") return "#e65100";
  return "#2e7d32";
}
