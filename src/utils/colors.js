// Category risk colours. Six-digit hex: FundCard appends alpha to them. Bright enough for dark and light themes.
export function getCategoryColor(risk) {
  const r = (risk || "").toLowerCase();
  if (r === "very high") return "#f43f5e";
  if (r === "high") return "#fb923c";
  if (r === "moderate") return "#fbbf24";
  return "#34d399";
}
