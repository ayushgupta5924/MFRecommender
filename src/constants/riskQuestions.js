// Risk profiling. Two things are scored separately, each 0-100:
//  - capacity: how much risk the investor's finances can absorb (age, income, dependents, loans, savings)
//  - willingness: how much risk they are comfortable with
// The plan uses the lower of the two, so a bold attitude can't push someone into
// more risk than their finances support. Each option carries 0-4 points, and some
// answers cap a score outright: no emergency savings means low capacity whatever else is true.

export const CAPACITY_QUESTIONS = [
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
    id: "dependents",
    question: "How many people depend on your income?",
    options: [
      { label: "None", points: 4, value: 0 },
      { label: "1 – 2", points: 2, value: 2 },
      { label: "3 or more", points: 1, value: 3 },
    ],
  },
  {
    id: "emergency",
    question: "How many months of expenses do you have saved for emergencies?",
    options: [
      { label: "More than 6 months", points: 4, value: 6 },
      { label: "3 – 6 months", points: 3, value: 3 },
      { label: "1 – 3 months", points: 1, value: 1 },
      { label: "None", points: 0, value: 0, capScore: 45 },
    ],
  },
];

export const INSURANCE_QUESTIONS = [
  { id: "health", question: "Do you have health insurance (your own or from your employer)?" },
  { id: "term", question: "Do you have term life insurance?" },
];

export const WILLINGNESS_QUESTIONS = [
  {
    id: "drawdown",
    question: "You invest ₹1,00,000. A month later it's worth ₹80,000. What do you do?",
    options: [
      { label: "Invest more while prices are low", points: 4 },
      { label: "Stay invested and wait", points: 3 },
      { label: "Sell some to limit losses", points: 1, capScore: 60 },
      { label: "Sell everything", points: 0, capScore: 35 },
    ],
  },
  {
    id: "range",
    question: "You invest ₹1,00,000 for a year. Which range of outcomes would you pick?",
    options: [
      { label: "₹1,06,000 to ₹1,08,000 (no chance of loss)", points: 0 },
      { label: "₹95,000 to ₹1,20,000", points: 2 },
      { label: "₹85,000 to ₹1,30,000", points: 3 },
      { label: "₹70,000 to ₹1,45,000", points: 4 },
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

export function riskLabel(score) {
  const tolerance = score < 35 ? "low" : score < 70 ? "moderate" : "high";
  const label = score < 35 ? "Conservative" : score < 70 ? "Moderate" : "Aggressive";
  return { tolerance, label };
}

// Adds up the chosen options; returns null until every question is answered.
function tally(questions, answers) {
  let points = 0;
  let cap = 100;
  for (const q of questions) {
    const opt = q.options[answers[q.id]];
    if (!opt) return null;
    points += opt.points;
    if (opt.capScore != null) cap = Math.min(cap, opt.capScore);
  }
  return { points, max: questions.length * 4, cap };
}

function agePoints(age) {
  return age < 30 ? 4 : age < 40 ? 3 : age < 50 ? 2 : age < 60 ? 1 : 0;
}

// Share of income going to EMIs. Above half, there's little room to absorb a loss.
function emiPoints(income, emi) {
  const ratio = income > 0 ? emi / income : emi > 0 ? Infinity : 0;
  if (ratio < 0.1) return { points: 4 };
  if (ratio < 0.25) return { points: 3 };
  if (ratio < 0.4) return { points: 2 };
  if (ratio <= 0.5) return { points: 1 };
  return { points: 0, cap: 50 };
}

export function scoreCapacity({ age, income, emi, answers }) {
  const t = tally(CAPACITY_QUESTIONS, answers);
  if (!t || !(age > 0) || !(income >= 0)) return null;
  const e = emiPoints(income, emi || 0);
  const points = t.points + agePoints(age) + e.points;
  const max = t.max + 8;
  return Math.min(Math.round((points / max) * 100), t.cap, e.cap ?? 100);
}

export function scoreWillingness(answers) {
  const t = tally(WILLINGNESS_QUESTIONS, answers);
  return t && Math.min(Math.round((t.points / t.max) * 100), t.cap);
}

export function scoreRisk(capacity, willingness) {
  if (capacity == null || willingness == null) return null;
  const score = Math.min(capacity, willingness);
  const limitedBy = capacity === willingness ? null : capacity < willingness ? "capacity" : "willingness";
  return { score, capacity, willingness, limitedBy, ...riskLabel(score) };
}
