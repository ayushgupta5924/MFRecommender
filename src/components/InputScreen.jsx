import { useState } from "react";
import { getPortfolio } from "../api";
import {
  CAPACITY_QUESTIONS, INSURANCE_QUESTIONS, WILLINGNESS_QUESTIONS,
  scoreCapacity, scoreRisk, scoreWillingness,
} from "../constants/riskQuestions";
import { fmt, requiredSip, sipFutureValue } from "../utils/format";
import { profileChecks } from "../utils/profileChecks";
import "../styles/InputScreen.css";
import "../styles/shared.css";

const LIFE_STAGES = [
  { value: "just_started",     emoji: "🎓", label: "Just started working",    desc: "First job, building habits" },
  { value: "recently_married", emoji: "💍", label: "Recently married",         desc: "Building a life together" },
  { value: "new_parent",       emoji: "👶", label: "New parent",               desc: "Planning for the family" },
  { value: "home_buyer",       emoji: "🏠", label: "Planning home purchase",   desc: "Saving for down payment" },
  { value: "peak_earning",     emoji: "📈", label: "Peak earning years",       desc: "Maximising wealth creation" },
  { value: "near_retirement",  emoji: "🎯", label: "5 years from retirement",  desc: "Protecting what I built" },
  { value: "retired",          emoji: "🧓", label: "Retired",                  desc: "Income & capital safety" },
];

const GOALS = [
  { value: "financial_freedom", emoji: "🏖️", label: "Financial Freedom",   desc: "Achieve financial independence", years: 15 },
  { value: "buy_home",          emoji: "🏠", label: "Buy a Home",           desc: "Save for down payment",          years: 5 },
  { value: "child_education",   emoji: "🎓", label: "Child's Education",    desc: "Build education corpus",         years: 12 },
  { value: "retirement",        emoji: "💼", label: "Retirement Corpus",    desc: "Long-term retirement fund",      years: 20 },
  { value: "tax_saving",        emoji: "🛡️", label: "Tax Saving",           desc: "Save tax under Section 80C",     years: 5 },
  { value: "emergency_corpus",  emoji: "⚡", label: "Emergency Corpus",     desc: "3–6 months safety net",          years: 1 },
  { value: "wealth_creation",   emoji: "📈", label: "Wealth Creation",      desc: "Grow money over the long term",  years: 10 },
];

// Goals with a real date attached, where it matters whether the date can move.
const DATED_GOALS = ["buy_home", "child_education", "retirement", "financial_freedom"];
const YEARS_LABEL = {
  buy_home: "When do you plan to buy? (years from now)",
  financial_freedom: "In how many years do you want to be financially free?",
};
const COLLEGE_AGE = 18;
const INFLATION = 0.06;
const STEPS = 6;

const RISK_COLORS = { Conservative: "#388e3c", Moderate: "#f57c00", Aggressive: "#d32f2f" };

// Rough rates for the live preview only; the final plan uses each fund category's history.
const INDICATIVE_RETURN = { Conservative: 0.075, Moderate: 0.095, Aggressive: 0.11 };

const num = (v) => (v === "" || v == null ? null : Number(v));

function NumberField({ id, label, value, onChange, icon = "₹", placeholder, hint, error, min = 0, max }) {
  return (
    <div className="fieldWrap">
      <label className="fieldLabel" htmlFor={id}>{label}</label>
      <div style={{ position: "relative" }}>
        <span className="fieldIcon">{icon}</span>
        <input id={id} type="number" min={min} max={max} value={value} onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder} className="fieldInput" />
      </div>
      {error ? <div className="fieldHint fieldHint--error">{error}</div> : hint && <div className="fieldHint">{hint}</div>}
    </div>
  );
}

function Choice({ options, value, onChange }) {
  return (
    <div className="quizOptions">
      {options.map(([v, l]) => (
        <button type="button" key={String(v)} className={`quizOption ${value === v ? "quizOption--selected" : ""}`}
          onClick={() => onChange(v)}>{l}</button>
      ))}
    </div>
  );
}

function Quiz({ questions, answers, setAnswers, start = 1 }) {
  return questions.map((q, qi) => (
    <div key={q.id} className="card quizCard">
      <div className="quizQuestion">{start + qi}. {q.question}</div>
      <Choice options={q.options.map((o, oi) => [oi, o.label])} value={answers[q.id]}
        onChange={(oi) => setAnswers((a) => ({ ...a, [q.id]: oi }))} />
    </div>
  ));
}

function ReviewSection({ title, step, onEdit, rows }) {
  return (
    <div className="card reviewCard">
      <div className="reviewCard__head">
        <span className="reviewCard__title">{title}</span>
        <button type="button" className="reviewCard__edit" onClick={() => onEdit(step)}>Edit</button>
      </div>
      {rows.filter(Boolean).map(([k, v]) => (
        <div key={k} className="reviewRow"><span>{k}</span><span>{v}</span></div>
      ))}
    </div>
  );
}

export default function InputScreen({ onBack, onResults }) {
  const [step, setStep]             = useState(1);
  const [age, setAge]               = useState("");
  const [lifeStage, setLifeStage]   = useState("");
  const [goal, setGoal]             = useState("");
  const [years, setYears]           = useState("");
  const [childAge, setChildAge]     = useState("");
  const [retireAge, setRetireAge]   = useState("60");
  const [fixedDeadline, setFixed]   = useState(null);
  const [income, setIncome]         = useState("");
  const [expenses, setExpenses]     = useState("");
  const [emi, setEmi]               = useState("");
  const [answers, setAnswers]       = useState({});
  const [insurance, setInsurance]   = useState({});
  const [budget, setBudget]         = useState("");
  const [targetAmount, setTarget]   = useState("");
  const [targetToday, setTargetToday] = useState(true);
  const [taxRegime, setTaxRegime]   = useState("old");
  const [consent, setConsent]       = useState(false);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");

  const ageValue = num(age);
  const ageValid = ageValue != null && ageValue >= 18 && ageValue <= 100;
  const goalInfo = GOALS.find((g) => g.value === goal);

  // Horizon comes from the goal's own details where we can work it out.
  let horizon = parseInt(years) || 0;
  if (goal === "emergency_corpus") horizon = 1;
  if (goal === "child_education") horizon = childAge === "" ? 0 : Math.max(1, COLLEGE_AGE - Number(childAge));
  if (goal === "retirement") horizon = ageValid && retireAge ? Number(retireAge) - ageValue : 0;
  const horizonValid = horizon >= 1 && horizon <= 40;
  const childAgeValid = goal !== "child_education" || (childAge !== "" && Number(childAge) >= 0 && Number(childAge) < COLLEGE_AGE);

  const incomeValue = num(income);
  const emiValue = num(emi) || 0;
  const surplus = incomeValue != null && expenses !== "" ? incomeValue - Number(expenses) - emiValue : null;

  const capacity = scoreCapacity({ age: ageValue, income: incomeValue, emi: emiValue, answers });
  const willingness = scoreWillingness(answers);
  const risk = scoreRisk(capacity, willingness);

  const rate = INDICATIVE_RETURN[risk?.label] || 0.09;
  const targetValue = num(targetAmount);
  const targetFuture = targetValue && horizon ? (targetToday ? targetValue * (1 + INFLATION) ** horizon : targetValue) : null;
  const sipNeeded = targetFuture ? Math.ceil(requiredSip(targetFuture, horizon, rate) / 100) * 100 : null;
  const budgetValue = num(budget) || 0;
  const fvOfBudget = budgetValue && horizon ? sipFutureValue(budgetValue, horizon, rate) : null;
  const sip = budgetValue >= 500 ? budgetValue : sipNeeded || 0;

  const amountValid = (budgetValue >= 500 || sipNeeded > 0) && !(budget && budgetValue < 500);
  const canProceed = {
    1: ageValid && !!lifeStage,
    2: !!goal && horizonValid && childAgeValid && (!DATED_GOALS.includes(goal) || fixedDeadline != null),
    3: incomeValue != null && expenses !== "" && capacity != null && INSURANCE_QUESTIONS.every((q) => insurance[q.id] != null),
    4: willingness != null,
    5: amountValid,
    6: consent,
  };

  const checks = risk ? profileChecks({ age, lifeStage, goal, horizon, risk, answers, surplus, sip }) : [];

  const chooseGoal = (g) => {
    setGoal(g.value);
    if (!years) setYears(String(g.years));
  };

  const handleSubmit = async () => {
    setError(""); setLoading(true);
    try {
      const pick = (id) => CAPACITY_QUESTIONS.find((q) => q.id === id).options[answers[id]].value;
      const payload = {
        life_stage:            lifeStage,
        goal:                  goal,
        risk_tolerance:        risk.tolerance,
        risk_score:            risk.score,
        capacity_score:        risk.capacity,
        willingness_score:     risk.willingness,
        monthly_budget:        budgetValue || null,
        target_amount:         targetValue || null,
        target_years:          targetValue ? horizon : null,
        target_in_today_value: !!targetValue && targetToday,
        horizon_years:         horizon,
        fixed_deadline:        DATED_GOALS.includes(goal) ? fixedDeadline : null,
        tax_regime:            goal === "tax_saving" ? taxRegime : null,
        age:                   ageValue,
        monthly_income:        incomeValue,
        monthly_expenses:      Number(expenses),
        monthly_emi:           emiValue,
        dependents:            pick("dependents"),
        emergency_months:      pick("emergency"),
        has_health_insurance:  insurance.health,
        has_term_insurance:    insurance.term,
      };
      const data = await getPortfolio(payload);
      onResults(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const yesNo = (v) => (v ? "Yes" : "No");
  const optLabel = (id) => {
    const q = [...CAPACITY_QUESTIONS, ...WILLINGNESS_QUESTIONS].find((x) => x.id === id);
    return q.options[answers[id]]?.label;
  };

  return (
    <div className="page">
      <div className="appBar">
        <button className="backBtn" aria-label="Back" onClick={step === 1 ? onBack : () => setStep(s => s - 1)}>←</button>
        <span className="appBar__title">Your Investor Profile</span>
        <span className="stepBadge">Step {step} of {STEPS}</span>
      </div>

      <div className="progressBar">
        <div className="progressBar__fill" style={{ width: `${(step / STEPS) * 100}%` }} />
      </div>

      <div className="body">

        {/* ── Step 1: About you ── */}
        {step === 1 && (
          <div>
            <div className="stepTitle">About you</div>
            <div className="stepSubtitle">Your age and stage of life shape how long your money can stay invested</div>
            <div className="card">
              <NumberField id="age" label="Your age" icon="🎂" value={age} onChange={setAge} min={18} max={100}
                placeholder="e.g. 32" error={age && !ageValid ? "Enter an age between 18 and 100." : null} />
            </div>
            <div className="stageGrid">
              {LIFE_STAGES.map((s) => (
                <button type="button" key={s.value}
                  onClick={() => setLifeStage(s.value)}
                  className={`stageCard ${lifeStage === s.value ? "stageCard--selected" : ""}`}>
                  <div className="stageCard__emoji">{s.emoji}</div>
                  <div className="stageCard__label">{s.label}</div>
                  <div className="stageCard__desc">{s.desc}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Step 2: Goal ── */}
        {step === 2 && (
          <div>
            <div className="stepTitle">What's your primary goal?</div>
            <div className="stepSubtitle">We'll build a portfolio specifically for this</div>
            <div className="goalGrid">
              {GOALS.map((g) => (
                <button type="button" key={g.value}
                  onClick={() => chooseGoal(g)}
                  className={`goalCard ${goal === g.value ? "goalCard--selected" : ""}`}>
                  <div className="goalCard__emoji">{g.emoji}</div>
                  <div className="goalCard__label">{g.label}</div>
                  <div className="goalCard__desc">{g.desc}</div>
                </button>
              ))}
            </div>

            {goal && (
              <div className="card">
                <div className="card__title">{goalInfo.emoji} About this goal</div>

                {goal === "emergency_corpus" && (
                  <div className="fieldHint">Emergency money must be available any day, so it stays in liquid and money market funds.</div>
                )}
                {goal === "child_education" && (
                  <NumberField id="childAge" label="Your child's age today" icon="👶" value={childAge} onChange={setChildAge}
                    min={0} max={17} placeholder="e.g. 4"
                    error={childAge !== "" && !childAgeValid ? `Enter an age under ${COLLEGE_AGE}.` : null}
                    hint={childAgeValid && childAge !== "" ? `College is about ${horizon} year${horizon !== 1 ? "s" : ""} away.` : null} />
                )}
                {goal === "retirement" && (
                  <NumberField id="retireAge" label="Age you want to retire at" icon="🧓" value={retireAge} onChange={setRetireAge}
                    min={30} max={80} placeholder="e.g. 60"
                    error={retireAge && !horizonValid ? `Enter an age between ${ageValue + 1} and ${ageValue + 40}.` : null}
                    hint={horizonValid ? `That's ${horizon} years from now.` : null} />
                )}
                {!["emergency_corpus", "child_education", "retirement"].includes(goal) && (
                  <NumberField id="years" label={YEARS_LABEL[goal] || "How many years will you invest for?"} icon="📅"
                    value={years} onChange={setYears} min={1} max={40} placeholder={`e.g. ${goalInfo.years}`}
                    error={years && !horizonValid ? "Enter between 1 and 40 years." : null} />
                )}

                {DATED_GOALS.includes(goal) && (
                  <div className="fieldWrap" style={{ marginBottom: 0 }}>
                    <div className="fieldLabel">If markets are down when the time comes, could you wait a year or two?</div>
                    <Choice value={fixedDeadline} onChange={setFixed}
                      options={[[false, "Yes, the date can move"], [true, "No, the date is fixed"]]} />
                    <div className="fieldHint">A fixed date means less equity as you get close, so a late fall can't hurt you.</div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Step 3: Finances ── */}
        {step === 3 && (
          <div>
            <div className="stepTitle">Your finances</div>
            <div className="stepSubtitle">This tells us how much risk you can afford, and whether this plan fits your budget. Nothing is stored.</div>

            <div className="card">
              <NumberField id="income" label="Monthly take-home income" value={income} onChange={setIncome} placeholder="e.g. 80000"
                hint="After tax. Enter 0 if you have no regular income." />
              <NumberField id="expenses" label="Monthly household expenses (excluding EMIs)" value={expenses} onChange={setExpenses}
                placeholder="e.g. 40000" />
              <NumberField id="emi" label="Monthly loan EMIs (home, car, personal, credit card)" value={emi} onChange={setEmi}
                placeholder="0 if none" />
              {surplus != null && (
                <div className={`fieldHint ${surplus <= 0 ? "fieldHint--error" : ""}`}>
                  {surplus > 0 ? `About ${fmt(surplus)} is left each month to invest.` : "Your expenses and EMIs use up all of your income."}
                </div>
              )}
            </div>

            <Quiz questions={CAPACITY_QUESTIONS} answers={answers} setAnswers={setAnswers} />

            {INSURANCE_QUESTIONS.map((q, qi) => (
              <div key={q.id} className="card quizCard">
                <div className="quizQuestion">{CAPACITY_QUESTIONS.length + qi + 1}. {q.question}</div>
                <Choice value={insurance[q.id]} onChange={(v) => setInsurance((s) => ({ ...s, [q.id]: v }))}
                  options={[[true, "Yes"], [false, "No"]]} />
              </div>
            ))}
          </div>
        )}

        {/* ── Step 4: Risk attitude ── */}
        {step === 4 && (
          <div>
            <div className="stepTitle">How you feel about risk</div>
            <div className="stepSubtitle">There are no right answers. Pick what you would actually do.</div>
            <Quiz questions={WILLINGNESS_QUESTIONS} answers={answers} setAnswers={setAnswers} />
            {risk && (
              <div className="riskResult" style={{ borderColor: RISK_COLORS[risk.label] }}>
                <div className="riskResult__label">Your risk profile</div>
                <div className="riskResult__value" style={{ color: RISK_COLORS[risk.label] }}>
                  {risk.label} <span className="riskResult__score">({risk.score}/100)</span>
                </div>
                <div className="riskSplit">
                  <span>Ability to take risk: <b>{risk.capacity}</b></span>
                  <span>Comfort with risk: <b>{risk.willingness}</b></span>
                </div>
                <div className="fieldHint">We use the lower of the two.</div>
              </div>
            )}
          </div>
        )}

        {/* ── Step 5: Amount ── */}
        {step === 5 && (
          <div>
            <div className="stepTitle">Let's do the math</div>
            <div className="stepSubtitle">
              Over {horizon} year{horizon !== 1 ? "s" : ""}. Enter a monthly amount, a target, or both.
            </div>

            <div className="card">
              <div className="card__title">🎯 Do you have a target amount in mind?</div>
              <NumberField id="target" label="Target amount" value={targetAmount} onChange={setTarget}
                placeholder="e.g. 2500000 (25 lakhs)" />
              {targetValue > 0 && (
                <div className="fieldWrap" style={{ marginBottom: 0 }}>
                  <div className="fieldLabel">Is that in today's prices?</div>
                  <Choice value={targetToday} onChange={setTargetToday}
                    options={[[true, "Yes, today's prices"], [false, "No, the amount I'll need then"]]} />
                  {targetToday && horizon > 0 && (
                    <div className="fieldHint">At {INFLATION * 100}% inflation that's about {fmt(targetFuture)} in {horizon} years.</div>
                  )}
                </div>
              )}
              {sipNeeded > 0 && (
                <div className="sipResult">
                  <div className="sipResult__label">Approximate monthly SIP needed</div>
                  <div className="sipResult__amount">{fmt(sipNeeded)}<span className="sipResult__month">/month</span></div>
                </div>
              )}
            </div>

            <div className="card">
              <div className="card__title">💰 How much will you invest monthly?</div>
              <NumberField id="budget" label="Monthly SIP" value={budget} onChange={setBudget}
                placeholder={sipNeeded ? `e.g. ${sipNeeded}` : "e.g. 10000"}
                error={budget && budgetValue < 500 ? "The minimum SIP is ₹500." : null}
                hint={!budget && sipNeeded ? "Leave blank to use the SIP needed for your target." : null} />
              {surplus != null && sip > 0 && (
                <div className={`fieldHint ${sip > surplus ? "fieldHint--error" : ""}`}>
                  {sip > surplus
                    ? `This is more than the ${fmt(Math.max(surplus, 0))} you have left each month.`
                    : `That's ${Math.round((sip / surplus) * 100)}% of what you have left each month.`}
                </div>
              )}
              {fvOfBudget > 0 && (
                <div className="sipResult">
                  <div className="sipResult__label">Rough estimate in {horizon} years</div>
                  <div className="sipResult__amount">{fmt(fvOfBudget)}</div>
                  <div className="sipResult__note">
                    At about {(rate * 100).toFixed(1)}% a year. Your plan will show a range based on real fund data.
                    {sipNeeded > 0 && (budgetValue >= sipNeeded ? " Looks enough for your target." : " May fall short of your target.")}
                  </div>
                </div>
              )}
            </div>

            {goal === "tax_saving" && (
              <div className="card">
                <div className="card__title">🧾 Which tax regime do you file under?</div>
                <Choice value={taxRegime} onChange={setTaxRegime}
                  options={[["old", "Old regime (80C deductions)"], ["new", "New regime"]]} />
                {taxRegime === "new" && <div className="fieldHint">ELSS gives no deduction under the new regime, so we'll use regular equity funds.</div>}
              </div>
            )}
          </div>
        )}

        {/* ── Step 6: Review ── */}
        {step === 6 && (
          <div>
            <div className="stepTitle">Check your answers</div>
            <div className="stepSubtitle">Your plan is built from these. Tap Edit to change anything.</div>

            {checks.length > 0 && (
              <div className="warningBox">
                <div className="warningBox__title">Worth a second look</div>
                {checks.map((c) => (
                  <div key={c.text} className="warningBox__item">
                    ⚠️ {c.text} <button type="button" className="linkBtn" onClick={() => setStep(c.step)}>Change</button>
                  </div>
                ))}
              </div>
            )}

            <ReviewSection title="About you" step={1} onEdit={setStep} rows={[
              ["Age", age],
              ["Life stage", LIFE_STAGES.find((s) => s.value === lifeStage)?.label],
            ]} />
            <ReviewSection title="Goal" step={2} onEdit={setStep} rows={[
              ["Goal", goalInfo?.label],
              ["Timeline", `${horizon} year${horizon !== 1 ? "s" : ""}`],
              DATED_GOALS.includes(goal) && ["Date", fixedDeadline ? "Fixed" : "Can move"],
            ]} />
            <ReviewSection title="Finances" step={3} onEdit={setStep} rows={[
              ["Take-home income", fmt(incomeValue)],
              ["Expenses + EMIs", fmt(Number(expenses) + emiValue)],
              ["Left each month", fmt(Math.max(surplus ?? 0, 0))],
              ["Income stability", optLabel("income")],
              ["Dependents", optLabel("dependents")],
              ["Emergency savings", optLabel("emergency")],
              ["Health / term insurance", `${yesNo(insurance.health)} / ${yesNo(insurance.term)}`],
            ]} />
            <ReviewSection title="Risk profile" step={4} onEdit={setStep} rows={[
              ["Ability to take risk", `${risk.capacity}/100`],
              ["Comfort with risk", `${risk.willingness}/100`],
              ["Profile used", `${risk.label} (${risk.score}/100)`],
            ]} />
            <ReviewSection title="Investment" step={5} onEdit={setStep} rows={[
              ["Monthly SIP", fmt(sip)],
              targetValue > 0 && ["Target", targetToday ? `${fmt(targetValue)} today ≈ ${fmt(targetFuture)} then` : fmt(targetValue)],
              goal === "tax_saving" && ["Tax regime", taxRegime === "old" ? "Old" : "New"],
            ]} />

            <label className="consentRow">
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>
                I confirm the information above is accurate and understand that mutual fund investments are subject to
                market risks and past performance does not guarantee future returns.
              </span>
            </label>
          </div>
        )}

        <div className="stepNav">
          {step < STEPS ? (
            <button className="btnBlue" onClick={() => setStep(s => s + 1)} disabled={!canProceed[step]}>
              {step === STEPS - 1 ? "Review →" : "Continue →"}
            </button>
          ) : (
            <button className="btnBlue" onClick={handleSubmit} disabled={loading || !canProceed[STEPS]}>
              {loading ? "Building your portfolio…" : "✨ Get My Portfolio"}
            </button>
          )}
          {loading && <div className="fieldHint" style={{ textAlign: "center" }}>If the server has been idle it can take up to a minute to wake up.</div>}
          {error && <div className="errorText">{error}</div>}
        </div>

      </div>
    </div>
  );
}
