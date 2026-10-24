export function fmt(n) {
  if (n == null || Number.isNaN(n)) return "—";
  if (n >= 10000000) return "₹" + (n / 10000000).toFixed(2) + " Cr";
  if (n >= 100000)   return "₹" + (n / 100000).toFixed(1) + " L";
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

export function pct(v, digits = 1) {
  return v == null ? "—" : `${v >= 0 ? "" : "−"}${Math.abs(v).toFixed(digits)}%`;
}

export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

// Future value of a SIP paid at the start of each month — same formula as the backend.
export function sipFutureValue(monthly, years, annualRate) {
  if (!monthly || !years) return 0;
  const i = Math.pow(1 + annualRate, 1 / 12) - 1;
  const n = years * 12;
  return i === 0 ? monthly * n : monthly * ((Math.pow(1 + i, n) - 1) / i) * (1 + i);
}

export function requiredSip(target, years, annualRate) {
  const unit = sipFutureValue(1, years, annualRate);
  return unit > 0 ? target / unit : 0;
}
