import { useState } from "react";
import { getPortfolio } from "../api";
import { RISK_QUESTIONS, scoreRisk } from "../constants/riskQuestions";
import { fmt, requiredSip, sipFutureValue } from "../utils/format";
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

const RISK_COLORS = { Conservative: "#388e3c", Moderate: "#f57c00", Aggressive: "#d32f2f" };

// Rough rates for the live preview only; the final plan uses each fund category's history.
const INDICATIVE_RETURN = { Conservative: 0.075, Moderate: 0.095, Aggressive: 0.11 };

export default function InputScreen({ onBack, onResults }) {
  const [step, setStep]             = useState(1);
  const [lifeStage, setLifeStage]   = useState("");
  const [goal, setGoal]             = useState("");
  const [answers, setAnswers]       = useState({});
  const [budget, setBudget]         = useState("");
  const [targetAmount, setTarget]   = useState("");
  const [years, setYears]           = useState("");
  const [taxRegime, setTaxRegime]   = useState("old");
  const [consent, setConsent]       = useState(false);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");

  const risk = scoreRisk(answers);
  const goalInfo = GOALS.find((g) => g.value === goal);
  const horizon = parseInt(years) || 0;
  const rate = INDICATIVE_RETURN[risk?.label] || 0.09;
  const sipNeeded = targetAmount && horizon ? Math.ceil(requiredSip(parseFloat(targetAmount), horizon, rate) / 100) * 100 : null;
  const fvOfBudget = budget && horizon ? sipFutureValue(parseFloat(budget), horizon, rate) : null;
  const budgetValue = parseFloat(budget) || 0;

  const amountValid = budgetValue >= 500 || (sipNeeded && sipNeeded > 0);
  const horizonValid = horizon >= 1 && horizon <= 40;
  const canProceed = {
    1: !!lifeStage,
    2: !!goal,
    3: !!risk,
    4: amountValid && horizonValid && consent && !(budget && budgetValue < 500),
  };

  const chooseGoal = (g) => {
    setGoal(g.value);
    if (!years) setYears(String(g.years));
  };

  const handleSubmit = async () => {
    setError(""); setLoading(true);
    try {
      const payload = {
        life_stage:      lifeStage,
        goal:            goal,
        risk_tolerance:  risk.tolerance,
        risk_score:      risk.score,
        monthly_budget:  budgetValue || null,
        target_amount:   targetAmount ? parseFloat(targetAmount) : null,
        target_years:    targetAmount ? horizon : null,
        horizon_years:   horizon,
        tax_regime:      goal === "tax_saving" ? taxRegime : null,
      };
      const data = await getPortfolio(payload);
      onResults(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="appBar">
        <button className="backBtn" aria-label="Back" onClick={step === 1 ? onBack : () => setStep(s => s - 1)}>←</button>
        <span className="appBar__title">Your Investor Profile</span>
        <span className="stepBadge">Step {step} of 4</span>
      </div>

      <div className="progressBar">
        <div className="progressBar__fill" style={{ width: `${(step / 4) * 100}%` }} />
      </div>

      <div className="body">

        {/* ── Step 1: Life Stage ── */}
        {step === 1 && (
          <div>
            <div className="stepTitle">What's your life stage?</div>
            <div className="stepSubtitle">This helps us understand your financial priorities</div>
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
          </div>
        )}

        {/* ── Step 3: Risk profile ── */}
        {step === 3 && (
          <div>
            <div className="stepTitle">Your risk profile</div>
            <div className="stepSubtitle">Answer honestly — this decides how much of your money goes into equity</div>
            {RISK_QUESTIONS.map((q, qi) => (
              <div key={q.id} className="card quizCard">
                <div className="quizQuestion">{qi + 1}. {q.question}</div>
                <div className="quizOptions">
                  {q.options.map((o, oi) => (
                    <button type="button" key={o.label}
                      className={`quizOption ${answers[q.id] === oi ? "quizOption--selected" : ""}`}
                      onClick={() => setAnswers((a) => ({ ...a, [q.id]: oi }))}>
                      {o.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {risk && (
              <div className="riskResult" style={{ borderColor: RISK_COLORS[risk.label] }}>
                <div className="riskResult__label">Your risk profile</div>
                <div className="riskResult__value" style={{ color: RISK_COLORS[risk.label] }}>
                  {risk.label} <span className="riskResult__score">({risk.score}/100)</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Step 4: Amount & horizon ── */}
        {step === 4 && (
          <div>
            <div className="stepTitle">Let's do the math</div>
            <div className="stepSubtitle">How long will you invest, and how much?</div>

            <div className="card">
              <div className="fieldWrap" style={{ marginBottom: 0 }}>
                <label className="fieldLabel" htmlFor="years">Investment horizon (years)</label>
                <div style={{ position: "relative" }}>
                  <span className="fieldIcon">📅</span>
                  <input id="years" type="number" min="1" max="40" value={years} onChange={e => setYears(e.target.value)}
                    placeholder={`e.g. ${goalInfo?.years || 10}`} className="fieldInput" />
                </div>
                {years && !horizonValid && <div className="fieldHint fieldHint--error">Enter between 1 and 40 years.</div>}
              </div>
            </div>

            <div className="card">
              <div className="card__title">💰 I'll invest this monthly</div>
              <div className="fieldWrap" style={{ marginBottom: 0 }}>
                <label className="fieldLabel" htmlFor="budget">Monthly SIP (₹)</label>
                <div style={{ position: "relative" }}>
                  <span className="fieldIcon">₹</span>
                  <input id="budget" type="number" min="500" value={budget} onChange={e => setBudget(e.target.value)}
                    placeholder="e.g. 10000" className="fieldInput" />
                </div>
                {budget && budgetValue < 500 && <div className="fieldHint fieldHint--error">The minimum SIP is ₹500.</div>}
              </div>
              {fvOfBudget > 0 && (
                <div className="sipResult">
                  <div className="sipResult__label">Rough estimate in {horizon} years</div>
                  <div className="sipResult__amount">{fmt(fvOfBudget)}</div>
                  <div className="sipResult__note">At about {(rate * 100).toFixed(1)}% a year. Your plan will show a range based on real fund data.</div>
                </div>
              )}
            </div>

            <div className="orDivider"><span>and / or</span></div>

            <div className="card">
              <div className="card__title">🎯 I want to reach a target</div>
              <div className="fieldWrap" style={{ marginBottom: 0 }}>
                <label className="fieldLabel" htmlFor="target">Target amount (₹)</label>
                <div style={{ position: "relative" }}>
                  <span className="fieldIcon">₹</span>
                  <input id="target" type="number" min="0" value={targetAmount} onChange={e => setTarget(e.target.value)}
                    placeholder="e.g. 5000000 (50 lakhs)" className="fieldInput" />
                </div>
              </div>
              {sipNeeded > 0 && (
                <div className="sipResult">
                  <div className="sipResult__label">Approximate monthly SIP needed</div>
                  <div className="sipResult__amount">{fmt(sipNeeded)}<span className="sipResult__month">/month</span></div>
                  <div className="sipResult__note">
                    {budgetValue >= 500
                      ? (budgetValue >= sipNeeded ? "Your monthly amount looks enough for this target." : "Your monthly amount may fall short; your plan will show the gap.")
                      : "We'll use this as your monthly amount."}
                  </div>
                </div>
              )}
            </div>

            {goal === "tax_saving" && (
              <div className="card">
                <div className="card__title">🧾 Which tax regime do you file under?</div>
                <div className="quizOptions">
                  {[["old", "Old regime (80C deductions)"], ["new", "New regime"]].map(([v, l]) => (
                    <button type="button" key={v} className={`quizOption ${taxRegime === v ? "quizOption--selected" : ""}`}
                      onClick={() => setTaxRegime(v)}>{l}</button>
                  ))}
                </div>
                {taxRegime === "new" && <div className="fieldHint">ELSS gives no deduction under the new regime, so we'll use regular equity funds.</div>}
              </div>
            )}

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
          {step < 4 ? (
            <button className="btnBlue" onClick={() => setStep(s => s + 1)} disabled={!canProceed[step]}>
              Continue →
            </button>
          ) : (
            <button className="btnBlue" onClick={handleSubmit} disabled={loading || !canProceed[4]}>
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
