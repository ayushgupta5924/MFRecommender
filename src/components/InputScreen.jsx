import { useState } from "react";
import { getPortfolio } from "../api";
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
  { value: "financial_freedom", emoji: "🏖️", label: "Financial Freedom",   desc: "Achieve financial independence" },
  { value: "buy_home",          emoji: "🏠", label: "Buy a Home",           desc: "Save for down payment" },
  { value: "child_education",   emoji: "🎓", label: "Child's Education",    desc: "Build education corpus" },
  { value: "retirement",        emoji: "💼", label: "Retirement Corpus",    desc: "Long-term retirement fund" },
  { value: "tax_saving",        emoji: "🛡️", label: "Tax Saving",           desc: "Save tax under Section 80C" },
  { value: "emergency_corpus",  emoji: "⚡", label: "Emergency Corpus",     desc: "3–6 months safety net" },
  { value: "wealth_creation",   emoji: "📈", label: "Wealth Creation",      desc: "Grow money aggressively" },
];

const RISK_OPTIONS = [
  { value: "low",      emoji: "🛡️", label: "Low",      desc: "I prefer safety over returns",         color: "#388e3c", bg: "rgba(56,142,60,0.08)" },
  { value: "moderate", emoji: "⚖️", label: "Moderate", desc: "Balance between safety and growth",    color: "#f57c00", bg: "rgba(245,124,0,0.08)" },
  { value: "high",     emoji: "📈", label: "High",     desc: "I can handle market ups and downs",    color: "#d32f2f", bg: "rgba(211,47,47,0.08)" },
];

const EXPECTED_RETURNS = { low: 0.07, moderate: 0.10, high: 0.13 };

function calcSIP(target, years, annualRate) {
  if (!target || !years || !annualRate) return 0;
  const r = annualRate / 12;
  const n = years * 12;
  return Math.round(target * r / (Math.pow(1 + r, n) - 1));
}

function calcFV(monthlySip, years, annualRate) {
  if (!monthlySip || !years || !annualRate) return 0;
  const r = annualRate / 12;
  const n = years * 12;
  return Math.round(monthlySip * (Math.pow(1 + r, n) - 1) / r * (1 + r));
}

function fmt(n) {
  if (!n) return "—";
  if (n >= 10000000) return "₹" + (n / 10000000).toFixed(1) + " Cr";
  if (n >= 100000)   return "₹" + (n / 100000).toFixed(1) + " L";
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

export default function InputScreen({ onBack, onResults }) {
  const [step, setStep]             = useState(1);
  const [lifeStage, setLifeStage]   = useState("");
  const [goal, setGoal]             = useState("");
  const [risk, setRisk]             = useState("");
  const [budget, setBudget]         = useState("");
  const [targetAmount, setTarget]   = useState("");
  const [targetYears, setYears]     = useState("");
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");

  const annualRate = EXPECTED_RETURNS[risk] || 0.10;
  const sipNeeded  = targetAmount && targetYears ? calcSIP(parseFloat(targetAmount), parseInt(targetYears), annualRate) : null;
  const fvOfBudget = budget && targetYears ? calcFV(parseFloat(budget), parseInt(targetYears), annualRate) : null;

  const canProceed = {
    1: !!lifeStage,
    2: !!goal,
    3: !!risk,
    4: !!(budget || (targetAmount && targetYears)),
  };

  const handleSubmit = async () => {
    setError(""); setLoading(true);
    try {
      const payload = {
        monthly_budget:  parseFloat(budget) || (sipNeeded || 1000),
        life_stage:      lifeStage,
        goal:            goal,
        risk_tolerance:  risk,
        target_amount:   targetAmount ? parseFloat(targetAmount) : null,
        target_years:    targetYears  ? parseInt(targetYears)    : null,
      };
      const data = await getPortfolio(payload);
      onResults(data, parseFloat(budget) || sipNeeded);
    } catch (e) {
      setError("Error: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="appBar">
        <button className="backBtn" onClick={step === 1 ? onBack : () => setStep(s => s - 1)}>←</button>
        <span className="appBar__title">Your Investor Profile</span>
        <span className="stepBadge">Step {step} of 4</span>
      </div>

      {/* Progress bar */}
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
                <div key={s.value}
                  onClick={() => setLifeStage(s.value)}
                  className={`stageCard ${lifeStage === s.value ? "stageCard--selected" : ""}`}>
                  <div className="stageCard__emoji">{s.emoji}</div>
                  <div className="stageCard__label">{s.label}</div>
                  <div className="stageCard__desc">{s.desc}</div>
                </div>
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
                <div key={g.value}
                  onClick={() => setGoal(g.value)}
                  className={`goalCard ${goal === g.value ? "goalCard--selected" : ""}`}>
                  <div className="goalCard__emoji">{g.emoji}</div>
                  <div className="goalCard__label">{g.label}</div>
                  <div className="goalCard__desc">{g.desc}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Step 3: Risk ── */}
        {step === 3 && (
          <div>
            <div className="stepTitle">What's your risk appetite?</div>
            <div className="stepSubtitle">Be honest — this determines your fund mix</div>
            {RISK_OPTIONS.map((r) => {
              const sel = risk === r.value;
              return (
                <div key={r.value} onClick={() => setRisk(r.value)}
                  className={`riskOption ${sel ? "riskOption--selected" : ""}`}
                  style={sel ? { borderColor: r.color, background: r.bg } : {}}>
                  <div className="riskIcon" style={sel ? { background: r.color } : {}}>{r.emoji}</div>
                  <div style={{ flex: 1 }}>
                    <div className="riskLabel" style={sel ? { color: r.color } : {}}>{r.label}</div>
                    <div className="riskDesc">{r.desc}</div>
                  </div>
                  <span style={{ fontSize: 22, color: sel ? r.color : "#ccc" }}>{sel ? "✅" : "⭕"}</span>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Step 4: SIP Calculator ── */}
        {step === 4 && (
          <div>
            <div className="stepTitle">Let's do the math</div>
            <div className="stepSubtitle">Tell us your target — we'll calculate what you need</div>

            {/* Goal-based calculator */}
            <div className="card">
              <div className="card__title">🎯 Goal-based calculator</div>
              <div className="fieldWrap">
                <label className="fieldLabel">I want to accumulate (₹)</label>
                <div style={{ position: "relative" }}>
                  <span className="fieldIcon">₹</span>
                  <input type="number" value={targetAmount} onChange={e => setTarget(e.target.value)}
                    placeholder="e.g. 5000000 (50 lakhs)" className="fieldInput" />
                </div>
              </div>
              <div className="fieldWrap">
                <label className="fieldLabel">In how many years?</label>
                <div style={{ position: "relative" }}>
                  <span className="fieldIcon">📅</span>
                  <input type="number" value={targetYears} onChange={e => setYears(e.target.value)}
                    placeholder="e.g. 10" className="fieldInput" />
                </div>
              </div>
              {sipNeeded > 0 && (
                <div className="sipResult">
                  <div className="sipResult__label">Monthly SIP required</div>
                  <div className="sipResult__amount">{fmt(sipNeeded)}<span className="sipResult__month">/month</span></div>
                  <div className="sipResult__note">
                    At {(annualRate * 100).toFixed(0)}% expected annual return ({risk} risk)
                  </div>
                </div>
              )}
            </div>

            <div className="orDivider"><span>or</span></div>

            {/* Monthly budget */}
            <div className="card">
              <div className="card__title">💰 I'll invest this monthly</div>
              <div className="fieldWrap" style={{ marginBottom: 0 }}>
                <label className="fieldLabel">Monthly investment (₹)</label>
                <div style={{ position: "relative" }}>
                  <span className="fieldIcon">₹</span>
                  <input type="number" value={budget} onChange={e => setBudget(e.target.value)}
                    placeholder="e.g. 10000" className="fieldInput" />
                </div>
              </div>
              {fvOfBudget > 0 && (
                <div className="sipResult">
                  <div className="sipResult__label">Estimated corpus in {targetYears || "—"} years</div>
                  <div className="sipResult__amount">{fmt(fvOfBudget)}</div>
                  <div className="sipResult__note">
                    At {(annualRate * 100).toFixed(0)}% expected annual return ({risk} risk)
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Nav buttons */}
        <div className="stepNav">
          {step < 4 ? (
            <button className="btnBlue" onClick={() => setStep(s => s + 1)} disabled={!canProceed[step]}>
              Continue →
            </button>
          ) : (
            <button className="btnBlue" onClick={handleSubmit} disabled={loading || (!budget && !sipNeeded)}>
              {loading ? "Building your portfolio…" : "✨ Get My Portfolio"}
            </button>
          )}
          {error && <div className="errorText">{error}</div>}
        </div>

      </div>
    </div>
  );
}