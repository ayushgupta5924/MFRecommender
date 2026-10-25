import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getHeldFunds, getPortfolio, searchFunds } from "../api";
import { useAuth } from "../auth";
import {
  CAPACITY_QUESTIONS, INSURANCE_QUESTIONS, WILLINGNESS_QUESTIONS,
  scoreCapacity, scoreRisk, scoreWillingness,
} from "../constants/riskQuestions";
import { fmt, requiredSip, sipFutureValue } from "../utils/format";
import { profileChecks } from "../utils/profileChecks";
import {
  GUEST_REVIEW_KEY, LAST_PLAN_KEY, clearPlanData, loadSession, save, usePersistentState,
} from "../utils/storage";
import AppBar from "./AppBar";
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

const RISK_COLORS = { Conservative: "var(--pos)", Moderate: "var(--warn)", Aggressive: "var(--neg)" };

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

// ── Funds already held ──────────────────────────────────────────────────────
// Taken from the portfolio review when there is one (this tab for a guest, the account when logged in);
// otherwise the investor is asked here.

function guestReviewFunds() {
  const saved = loadSession(GUEST_REVIEW_KEY, null);
  if (saved?.funds?.length) return saved.funds;
  return (saved?.holdings || []).filter((h) => h.code).map(({ code, name, units }) => ({ code, name, units }));
}

// null while we look, then a list (empty when there is no review).
function useReviewedFunds() {
  const { user } = useAuth();
  const [account, setAccount] = useState(null);
  const guest = useMemo(() => (user === null ? guestReviewFunds() : null), [user]);
  useEffect(() => {
    if (!user) return undefined;
    let live = true;
    getHeldFunds().then((f) => live && setAccount(f)).catch(() => live && setAccount([]));
    return () => { live = false; };
  }, [user]);
  return user ? account : guest;
}

function FundSearch({ onAdd, hasSome }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);
  const [fund, setFund] = useState(null);
  const [value, setValue] = useState("");

  useEffect(() => {
    if (fund || q.trim().length < 3) return undefined;
    let live = true;
    const t = setTimeout(() => {
      searchFunds(q.trim()).then((r) => live && setHits(r)).catch(() => live && setHits([]));
    }, 300);
    return () => { live = false; clearTimeout(t); };
  }, [q, fund]);

  const add = () => {
    onAdd({ code: fund.code, name: fund.name, value: Number(value) });
    setFund(null); setQ(""); setValue(""); setHits([]);
  };

  if (fund) {
    return (
      <div>
        <div className="pickedFund">
          <div>
            <div className="fundHit__name">{fund.name}</div>
            <div className="fundHit__meta">{fund.plan} · {fund.option} · {fund.amc}</div>
          </div>
          <button type="button" className="linkBtn" onClick={() => setFund(null)}>Change</button>
        </div>
        <NumberField id="heldValue" label="Its current value" value={value} onChange={setValue} placeholder="e.g. 150000"
          hint="From your fund app or latest statement." />
        <button type="button" className="btnOutline" disabled={!(Number(value) > 0)} onClick={add}>Add this fund</button>
      </div>
    );
  }
  return (
    <div className="fieldWrap">
      <label className="fieldLabel" htmlFor="heldQ">{hasSome ? "Add another fund" : "Search for a fund you hold"}</label>
      <input id="heldQ" className="fieldInput plainInput" value={q} onChange={(e) => setQ(e.target.value)}
        placeholder="e.g. Parag Parikh Flexi Cap" autoComplete="off" />
      {q.trim().length >= 3 && (
        <div className="fundHits" style={{ marginTop: 8 }}>
          {hits.length === 0 && <div className="mutedText">No matching funds yet. Try fewer words.</div>}
          {hits.map((h) => (
            <button type="button" key={h.code} className="fundHit" onClick={() => setFund(h)}>
              <span className="fundHit__name">{h.name}</span>
              <span className="fundHit__meta">{h.plan} · {h.option} · {h.amc}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function HeldFunds({ reviewed, hasFunds, setHasFunds, manual, setManual, count, setCount }) {
  const fromReview = reviewed?.length > 0;
  const shown = fromReview ? reviewed : manual;
  const n = reviewed?.length;
  return (
    <div className="card">
      <div className="card__title">📂 Funds you already hold</div>
      {reviewed === null ? <div className="fieldHint">Checking for funds from your portfolio review…</div> : (
        <>
          <div className="fieldLabel">
            {fromReview ? `We found ${n} fund${n !== 1 ? "s" : ""} from your portfolio review. Use them in this plan?`
              : "Do you already hold any mutual funds?"}
          </div>
          <Choice value={hasFunds} onChange={setHasFunds}
            options={fromReview ? [[true, "Yes, use them"], [false, "No, leave them out"]] : [[true, "Yes"], [false, "No"]]} />

          {hasFunds && shown.length > 0 && (
            <ul className="heldList">
              {shown.map((f) => (
                <li key={f.code}>
                  <span>{f.name}</span>
                  <span>
                    {f.value ? fmt(f.value) : `${Math.round(f.units * 100) / 100} units`}
                    {!fromReview && (
                      <button type="button" className="linkBtn" aria-label={`Remove ${f.name}`}
                        onClick={() => setManual(manual.filter((m) => m.code !== f.code))}>Remove</button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {hasFunds && !fromReview && (
            <>
              <FundSearch hasSome={manual.length > 0}
                onAdd={(f) => setManual([...manual.filter((m) => m.code !== f.code), f])} />
              <div className="fieldHint">
                Have your CAS statement? <Link to="/review">Upload it on the review page</Link> and come back: we'll use
                every fund in it here.
              </div>
            </>
          )}
          {hasFunds && shown.length > 0 && (
            <div className="fieldWrap" style={{ marginTop: 14, marginBottom: 0 }}>
              <div className="fieldLabel">Should they count towards this goal?</div>
              <Choice value={count} onChange={setCount}
                options={[[true, "Yes, count them"], [false, "No, they're for something else"]]} />
            </div>
          )}
          {hasFunds != null && (
            <div className="fieldHint">
              {hasFunds ? "With your plan you'll see each fund's rating and whether to keep it, watch it or move new SIPs elsewhere."
                : fromReview ? "The plan won't look at them." : "The plan starts from scratch."}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// Answers are kept in this browser so a refresh doesn't lose them.
const K = (name) => `mfa:plan:${name}`;

export default function InputScreen() {
  const navigate = useNavigate();
  const [step, setStep]             = usePersistentState(K("step"), 1);
  const [age, setAge]               = usePersistentState(K("age"), "");
  const [lifeStage, setLifeStage]   = usePersistentState(K("lifeStage"), "");
  const [goal, setGoal]             = usePersistentState(K("goal"), "");
  const [years, setYears]           = usePersistentState(K("years"), "");
  const [childAge, setChildAge]     = usePersistentState(K("childAge"), "");
  const [retireAge, setRetireAge]   = usePersistentState(K("retireAge"), "60");
  const [fixedDeadline, setFixed]   = usePersistentState(K("fixedDeadline"), null);
  const [income, setIncome]         = usePersistentState(K("income"), "");
  const [expenses, setExpenses]     = usePersistentState(K("expenses"), "");
  const [emi, setEmi]               = usePersistentState(K("emi"), "");
  const [answers, setAnswers]       = usePersistentState(K("answers"), {});
  const [insurance, setInsurance]   = usePersistentState(K("insurance"), {});
  const [budget, setBudget]         = usePersistentState(K("budget"), "");
  const [lump, setLump]             = usePersistentState(K("lump"), "");
  const [targetAmount, setTarget]   = usePersistentState(K("target"), "");
  const [targetToday, setTargetToday] = usePersistentState(K("targetToday"), true);
  const [taxRegime, setTaxRegime]   = usePersistentState(K("taxRegime"), "old");
  const [hasFunds, setHasFunds]     = usePersistentState(K("hasFunds"), null);
  const [manualFunds, setManualFunds] = usePersistentState(K("heldFunds"), []);
  const [countHeld, setCountHeld]   = usePersistentState(K("countHeld"), true);
  const reviewed                    = useReviewedFunds();
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
  const budgetValue = num(budget) || 0;
  const lumpValue = num(lump) || 0;
  const lumpFv = lumpValue && horizon ? lumpValue * (1 + rate) ** horizon : 0;
  const heldFunds = hasFunds ? (reviewed?.length ? reviewed : manualFunds) : [];
  // Funds known only by units are valued by the plan itself; the preview uses the values we have.
  const heldValue = heldFunds.reduce((s, f) => s + (f.value || 0), 0);
  const heldFv = countHeld && heldValue && horizon ? heldValue * (1 + rate) ** horizon : 0;
  // SIP still needed after the money already there has grown; 0 when that alone is enough.
  const remaining = targetFuture ? targetFuture - lumpFv - heldFv : null;
  const sipNeeded = remaining == null ? null : remaining > 0 ? Math.ceil(requiredSip(remaining, horizon, rate) / 100) * 100 : 0;
  const fvOfBudget = horizon ? (budgetValue ? sipFutureValue(budgetValue, horizon, rate) : 0) + lumpFv + heldFv : null;
  // With a one-time amount and no SIP entered, the plan is one-time only (as on the backend).
  const sip = budgetValue >= 500 ? budgetValue : lumpValue ? 0 : sipNeeded || 0;

  const amountValid = (budgetValue >= 500 || sipNeeded > 0 || lumpValue >= 1000)
    && !(budget && budgetValue < 500) && !(lump && lumpValue < 1000);
  const canProceed = {
    1: ageValid && !!lifeStage,
    2: !!goal && horizonValid && childAgeValid && (!DATED_GOALS.includes(goal) || fixedDeadline != null),
    3: incomeValue != null && expenses !== "" && capacity != null && INSURANCE_QUESTIONS.every((q) => insurance[q.id] != null),
    4: willingness != null,
    5: amountValid && reviewed !== null && hasFunds != null && (!hasFunds || heldFunds.length > 0),
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
        lump_sum:              lumpValue || null,
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
        // Units when we have them (valued at today's NAV), otherwise the value the investor entered.
        existing_holdings:     heldFunds.map(({ code, units, value }) => (units ? { code, units } : { code, value })),
        count_existing:        countHeld,
      };
      const data = await getPortfolio(payload);
      save(LAST_PLAN_KEY, { payload, results: data, savedId: null });
      navigate("/plan/results");
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
      <AppBar title="Your Investor Profile" onBack={step === 1 ? () => navigate("/") : () => setStep(s => s - 1)}
        extra={<span className="stepBadge">Step {step} of {STEPS}</span>} />

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
            <div className="stepSubtitle">This tells us how much risk you can afford, and whether this plan fits your budget. As SEBI requires, your answers and the plan we suggest are kept as a record of our advice (without your name unless you are logged in).</div>

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

            <HeldFunds reviewed={reviewed} hasFunds={hasFunds} setHasFunds={setHasFunds} manual={manualFunds}
              setManual={setManualFunds} count={countHeld} setCount={setCountHeld} />

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
              {sipNeeded === 0 && (lumpValue > 0 || heldFv > 0) && (
                <div className="fieldHint">
                  {heldFv > 0 ? "The funds you already hold" : "Your one-time amount"}{lumpValue > 0 && heldFv > 0 && " and your one-time amount"}
                  {" "}should be enough for this target. Enter a monthly or one-time amount if you want to invest more.
                </div>
              )}
              {sipNeeded > 0 && (
                <div className="sipResult">
                  <div className="sipResult__label">
                    Approximate monthly SIP needed
                    {heldFv > 0 ? " on top of the funds you hold" : lumpValue > 0 ? " on top of your one-time amount" : ""}
                  </div>
                  <div className="sipResult__amount">{fmt(sipNeeded)}<span className="sipResult__month">/month</span></div>
                </div>
              )}
            </div>

            <div className="card">
              <div className="card__title">💰 How much will you invest?</div>
              <NumberField id="budget" label="Monthly SIP" value={budget} onChange={setBudget}
                placeholder={sipNeeded ? `e.g. ${sipNeeded}` : "e.g. 10000"}
                error={budget && budgetValue < 500 ? "The minimum SIP is ₹500." : null}
                hint={budget ? null : lumpValue ? "Leave blank to invest only the one-time amount."
                  : sipNeeded ? "Leave blank to use the SIP needed for your target." : null} />
              <NumberField id="lump" label="One-time amount now (optional)" value={lump} onChange={setLump}
                placeholder="e.g. 200000"
                error={lump && lumpValue < 1000 ? "The minimum one-time amount is ₹1,000." : null}
                hint={lump ? null : "Money you have ready today, such as a bonus or a maturing FD."} />
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
              ["Monthly SIP", sip ? fmt(sip) : "None"],
              lumpValue > 0 && ["One-time amount", fmt(lumpValue)],
              targetValue > 0 && ["Target", targetToday ? `${fmt(targetValue)} today ≈ ${fmt(targetFuture)} then` : fmt(targetValue)],
              goal === "tax_saving" && ["Tax regime", taxRegime === "old" ? "Old" : "New"],
              ["Funds you hold", heldFunds.length
                ? `${heldFunds.length} fund${heldFunds.length !== 1 ? "s" : ""}${heldValue ? ` · ${fmt(heldValue)}` : ""} · ${countHeld ? "counted" : "not counted"}`
                : "None"],
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
          <button type="button" className="linkBtn clearAnswers" onClick={() => {
            if (!window.confirm("Clear all your answers from this browser?")) return;
            clearPlanData();
            window.location.reload();
          }}>
            Clear my answers
          </button>
          <div className="mutedText clearAnswersNote">Your answers are kept in this browser so a refresh doesn't lose them.</div>
        </div>

      </div>
    </div>
  );
}
