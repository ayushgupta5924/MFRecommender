import { fmt } from "./format";

const GROWTH_GOALS = ["wealth_creation", "financial_freedom"];
const PROTECT_CAPITAL = 4;   // index of "Protecting my capital" in the priority question

// Answers that pull in different directions. Shown on the review step so the
// investor can fix a mistake or confirm what they meant; each points to the step to edit.
export function profileChecks({ age, lifeStage, goal, horizon, risk, answers, surplus, sip }) {
  const out = [];
  const a = Number(age);

  if (lifeStage === "retired" && a < 45)
    out.push({ step: 1, text: `You chose "Retired" but you're ${a}. If you're still working, pick another life stage: it changes how much equity we use.` });
  if (lifeStage === "near_retirement" && a < 45)
    out.push({ step: 1, text: `You chose "5 years from retirement" at ${a}. If you plan to retire that early, check your retirement age on the goal step.` });
  if (lifeStage === "just_started" && a >= 45)
    out.push({ step: 1, text: `You chose "Just started working" at ${a}. Another life stage may describe you better.` });

  if (risk?.limitedBy === "capacity" && risk.willingness - risk.capacity >= 20)
    out.push({ step: 3, text: `You're comfortable with more risk (${risk.willingness}/100) than your finances can absorb right now (${risk.capacity}/100). We'll use the lower score.` });
  if (risk?.limitedBy === "willingness" && risk.capacity - risk.willingness >= 20)
    out.push({ step: 4, text: `Your finances could take more risk (${risk.capacity}/100) than you're comfortable with (${risk.willingness}/100). We'll go with your comfort level, which may mean slower growth.` });

  if (risk && horizon < 3 && risk.willingness >= 70)
    out.push({ step: 2, text: "You're comfortable with risk, but money needed within 3 years stays out of equity whatever your profile." });
  if (answers.priority === PROTECT_CAPITAL && GROWTH_GOALS.includes(goal) && horizon >= 7)
    out.push({ step: 4, text: "Your priority is protecting capital, but your goal is long-term growth. A low-risk plan grows slowly and may barely beat inflation." });

  if (surplus != null && sip > Math.max(surplus, 0))
    out.push({ step: 5, text: `Your SIP of ${fmt(sip)} is more than what's left each month after expenses and EMIs (${fmt(Math.max(surplus, 0))}).` });

  return out;
}
