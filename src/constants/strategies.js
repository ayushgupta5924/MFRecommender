export const FACTORS = [
  { title: "Risk Profile", desc: "A 6-question score of your ability and willingness to take risk", color: "#f57c00", bg: "rgba(245,124,0,0.08)", border: "rgba(245,124,0,0.25)", emoji: "📈" },
  { title: "Investment Horizon", desc: "How many years until you need the money", color: "#1976d2", bg: "rgba(25,118,210,0.08)", border: "rgba(25,118,210,0.25)", emoji: "⏱️" },
  { title: "Goal & Life Stage", desc: "Retirement, education, home, tax saving and more", color: "#388e3c", bg: "rgba(56,142,60,0.08)", border: "rgba(56,142,60,0.25)", emoji: "🎯" },
  { title: "Investment Amount", desc: "Sets how many funds you can hold sensibly", color: "#7b1fa2", bg: "rgba(123,31,162,0.08)", border: "rgba(123,31,162,0.25)", emoji: "₹" },
];

export const STRATEGIES = [
  {
    title: "1. Asset Allocation",
    color: "#f57c00",
    desc: "Your equity / hybrid / debt split is calculated from your risk score, horizon, life stage and goal:",
    points: [
      "Higher risk score and longer horizon → more equity",
      "Equity capped at 25% under 4 years, 35% under 5 years and 60% under 7 years",
      "Near retirement: max 50% equity · Retired: max 40% equity",
      "Under 3 years or emergency money → no equity at all",
    ],
  },
  {
    title: "2. Fund Universe",
    color: "#1976d2",
    desc: "Every open-ended Direct-Growth fund published by AMFI, refreshed daily:",
    points: [
      "Grouped by SEBI category: index, large, flexi, mid, small cap, ELSS, hybrid and debt",
      "Dividend (IDCW), closed-ended, segregated and stale funds are excluded",
      "Funds need at least 3 years of history (1–2 years for liquid and debt)",
    ],
  },
  {
    title: "3. Fund Ranking",
    color: "#388e3c",
    desc: "Each fund is scored against the other funds in its own category:",
    points: [
      "3- and 5-year annualised returns",
      "Consistency: median and worst-case rolling returns",
      "Risk: volatility, worst fall and downside-adjusted return (Sortino)",
      "Conservative profiles weight safety more; aggressive profiles weight returns more",
    ],
  },
  {
    title: "4. Portfolio Construction",
    color: "#7b1fa2",
    desc: "The final plan is kept simple and diversified:",
    points: [
      "2 funds under ₹3,000/month, up to 6 funds above ₹50,000/month",
      "Every SIP at least ₹500",
      "Picks are spread across different fund houses",
      "Projections use category-level returns, shown as a range",
    ],
  },
];
