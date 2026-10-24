// Risk profiling questionnaire. Each option carries 0-4 points; the total is
// scaled to a 0-100 score. Capacity answers can cap the score, because someone
// with no emergency savings shouldn't take high risk whatever their attitude.
export const RISK_QUESTIONS = [
  {
    id: "age",
    question: "How old are you?",
    options: [
      { label: "Under 30", points: 4 },
      { label: "30 – 40", points: 3 },
      { label: "40 – 50", points: 2 },
      { label: "50 – 60", points: 1 },
      { label: "Over 60", points: 0 },
    ],
  },
  {
    id: "income",
    question: "How stable is your income?",
    options: [
      { label: "Very stable (government / large employer)", points: 4 },
      { label: "Stable salaried job", points: 3 },
      { label: "Business or variable income", points: 2 },
      { label: "Irregular income", points: 1 },
      { label: "No regular income / retired", points: 0 },
    ],
  },
  {
    id: "emergency",
    question: "How many months of expenses do you have saved for emergencies?",
    options: [
      { label: "More than 6 months", points: 4 },
      { label: "3 – 6 months", points: 3 },
      { label: "1 – 3 months", points: 1 },
      { label: "None", points: 0, capScore: 45 },
    ],
  },
  {
    id: "drawdown",
    question: "Your investments fall 20% in a month. What do you do?",
    options: [
      { label: "Invest more while prices are low", points: 4 },
      { label: "Stay invested and wait", points: 3 },
      { label: "Sell some to limit losses", points: 1, capScore: 60 },
      { label: "Sell everything", points: 0, capScore: 35 },
    ],
  },
  {
    id: "experience",
    question: "How much experience do you have with equity investing?",
    options: [
      { label: "5+ years in stocks or equity funds", points: 4 },
      { label: "1 – 5 years", points: 3 },
      { label: "Less than a year", points: 1 },
      { label: "None", points: 0 },
    ],
  },
  {
    id: "priority",
    question: "What matters most to you?",
    options: [
      { label: "Maximum growth, I can accept big swings", points: 4 },
      { label: "Growth, with some stability", points: 3 },
      { label: "An even balance", points: 2 },
      { label: "Stability, with a little growth", points: 1 },
      { label: "Protecting my capital", points: 0 },
    ],
  },
];

export function scoreRisk(answers) {
  const max = RISK_QUESTIONS.length * 4;
  let points = 0;
  let cap = 100;
  for (const q of RISK_QUESTIONS) {
    const opt = q.options[answers[q.id]];
    if (!opt) return null;
    points += opt.points;
    if (opt.capScore != null) cap = Math.min(cap, opt.capScore);
  }
  const score = Math.min(Math.round((points / max) * 100), cap);
  const tolerance = score < 35 ? "low" : score < 70 ? "moderate" : "high";
  const label = score < 35 ? "Conservative" : score < 70 ? "Moderate" : "Aggressive";
  return { score, tolerance, label };
}
