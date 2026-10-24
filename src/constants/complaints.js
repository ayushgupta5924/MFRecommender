// Complaints data in SEBI's format (Annexure B, circular SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/80).
// UPDATE BY THE 7TH OF EVERY MONTH: set monthEnding, fill `rows` for the month just ended, add that month to
// `monthly` (April to March of the current financial year), and roll `annual` forward each April.
// The figures below are zero because the service has not yet started taking clients.

export const COMPLAINTS = {
  monthEnding: "30 September 2026",
  // Per source: pending at end of last month, received, resolved (incl. earlier months'), total pending,
  // pending more than 3 months, average resolution time in days (null when nothing was resolved).
  rows: [
    { source: "Directly from Investors", pendingStart: 0, received: 0, resolved: 0, pending: 0, over3Months: 0, avgDays: null },
    { source: "SEBI (SCORES)",           pendingStart: 0, received: 0, resolved: 0, pending: 0, over3Months: 0, avgDays: null },
    { source: "Other Sources (if any)",  pendingStart: 0, received: 0, resolved: 0, pending: 0, over3Months: 0, avgDays: null },
  ],
  impersonation: 0,
  monthly: [
    { month: "April, 2026",     carried: 0, received: 0, resolved: 0, pending: 0 },
    { month: "May, 2026",       carried: 0, received: 0, resolved: 0, pending: 0 },
    { month: "June, 2026",      carried: 0, received: 0, resolved: 0, pending: 0 },
    { month: "July, 2026",      carried: 0, received: 0, resolved: 0, pending: 0 },
    { month: "August, 2026",    carried: 0, received: 0, resolved: 0, pending: 0 },
    { month: "September, 2026", carried: 0, received: 0, resolved: 0, pending: 0 },
  ],
  annual: [
    { year: "2025-26", carried: 0, received: 0, resolved: 0, pending: 0 },
  ],
};
