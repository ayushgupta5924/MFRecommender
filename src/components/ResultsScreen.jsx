import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { getPortfolio, savePlan } from "../api";
import { useAuth } from "../auth";
import "../styles/FundCard.css";
import "../styles/ResultsScreen.css";
import "../styles/shared.css";
import { fmt, fmtDate } from "../utils/format";
import { LAST_PLAN_KEY, load, save } from "../utils/storage";
import AppBar from "./AppBar";
import Disclaimer from "./Disclaimer";
import FundCard from "./FundCard";

const MIX_COLORS = { equity: "#d32f2f", hybrid: "#f57c00", debt: "#388e3c" };
const MIX_LABELS = { equity: "Equity", hybrid: "Hybrid", debt: "Debt" };
const SCENARIOS = [
  ["pessimistic", "If markets disappoint"],
  ["expected", "Expected"],
  ["optimistic", "If markets do well"],
];

function SavePlan({ last, setLast }) {
  const { user, accountsEnabled } = useAuth();
  const [state, setState] = useState({ saving: false, error: "" });

  if (!accountsEnabled) return null;
  if (user === null) {
    return (
      <Link className="btnOutline" to={`/login?next=${encodeURIComponent("/plan/results")}`}>
        🔐 Log in to save this plan
      </Link>
    );
  }
  if (last.savedId) {
    return <div className="successText">✅ Saved to your account. <Link to="/account">See your plans</Link></div>;
  }
  const onSave = async () => {
    setState({ saving: true, error: "" });
    try {
      const saved = await savePlan(last.payload, last.results);
      const next = { ...last, savedId: saved.id };
      save(LAST_PLAN_KEY, next);
      setLast(next);
    } catch (e) {
      setState({ saving: false, error: e.message });
      return;
    }
    setState({ saving: false, error: "" });
  };
  return (
    <>
      <button className="btnOutline" onClick={onSave} disabled={state.saving || !user}>
        {state.saving ? "Saving…" : "💾 Save to my account"}
      </button>
      {state.error && <div className="errorText">{state.error}</div>}
    </>
  );
}

// Re-run the plan with different amounts or timeline. The questionnaire answers stay as they were;
// "Reset" goes back to them.
function WhatIf({ last, setLast }) {
  // The numbers of the plan as first built from the questionnaire.
  const base = last.base || { sip: last.results.monthly_investment || 0, lump: last.results.lump_sum || 0,
                              years: last.results.horizon_years };
  const [open, setOpen] = useState(false);
  const [sip, setSip] = useState(last.results.monthly_investment || 0);
  const [lump, setLump] = useState(last.results.lump_sum || 0);
  const [years, setYears] = useState(last.results.horizon_years);
  const [state, setState] = useState({ busy: false, error: "" });

  const sipError = sip > 0 && sip < 500 ? "The minimum SIP is ₹500." : "";
  const lumpError = lump > 0 && lump < 1000 ? "The minimum one-time amount is ₹1,000." : "";
  const emptyError = !sip && !lump ? "Enter a monthly SIP or a one-time amount." : "";
  const problem = sipError || lumpError || emptyError;

  useEffect(() => {
    // Only re-run when the numbers differ from the plan on screen.
    const r = last.results;
    if (problem || (sip === r.monthly_investment && lump === (r.lump_sum || 0) && years === r.horizon_years)) return undefined;
    const t = setTimeout(async () => {
      setState({ busy: true, error: "" });
      const payload = { ...last.payload, monthly_budget: sip || null, lump_sum: lump || null, horizon_years: years,
                        target_years: last.payload.target_amount ? years : null };
      try {
        const results = await getPortfolio(payload);
        const next = { payload, results, savedId: null, base };
        save(LAST_PLAN_KEY, next);
        setLast(next);
        setState({ busy: false, error: "" });
      } catch (e) {
        setState({ busy: false, error: e.message });
      }
    }, 600);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sip, lump, years]);

  const reset = () => {
    setSip(base.sip);
    setLump(base.lump);
    setYears(base.years);
  };
  const maxSip = Math.max(100_000, Math.ceil(base.sip * 2 / 1000) * 1000);

  if (!open) {
    return <button className="btnOutline whatIfToggle" onClick={() => setOpen(true)}>🎚️ Try different numbers</button>;
  }
  return (
    <div className="card whatIf">
      <div className="whatIf__head">
        <div className="card__title" style={{ marginBottom: 0 }}>Try different numbers</div>
        <span className="mutedText">{state.busy ? "Updating…" : ""}</span>
      </div>
      <label className="whatIf__row">
        <span>Monthly SIP <b>{sip ? fmt(sip) : "None"}</b></span>
        <input type="range" min="0" max={maxSip} step="500" value={sip} onChange={(e) => setSip(Number(e.target.value))} />
      </label>
      <label className="whatIf__row">
        <span>Timeline <b>{years} year{years !== 1 ? "s" : ""}</b></span>
        <input type="range" min="1" max="40" step="1" value={years} onChange={(e) => setYears(Number(e.target.value))} />
      </label>
      <div className="whatIf__row">
        <label htmlFor="whatIfLump">One-time amount</label>
        <input id="whatIfLump" type="number" min="0" step="1000" className="fieldInput whatIf__input" value={lump || ""}
          placeholder="0" onChange={(e) => setLump(Number(e.target.value) || 0)} />
      </div>
      {(problem || state.error) && <div className="errorText">{problem || state.error}</div>}
      <div className="whatIf__foot">
        <span className="mutedText">Your risk profile and goal stay the same. A shorter timeline can lower equity.</span>
        <button className="linkBtn" onClick={reset}>Reset to my answers</button>
      </div>
    </div>
  );
}

export default function ResultsScreen() {
  const navigate = useNavigate();
  const { accountsEnabled } = useAuth();
  const [last, setLast] = useState(() => load(LAST_PLAN_KEY, null));
  if (!last?.results) return <Navigate to="/plan" replace />;
  const results = last.results;
  const onBack = () => navigate("/plan");
  const funds = results?.funds || [];
  const mix = results?.asset_mix || {};
  const projections = results?.projections || {};
  const years = results?.horizon_years;
  const risk = results?.risk_profile;
  const target = results?.target_amount_today
    ? `${fmt(results.target_amount)} (${fmt(results.target_amount_today)} in today's money)`
    : fmt(results?.target_amount);

  return (
    <div className="page">
      <AppBar title="Your Plan" onBack={onBack} />

      <div className="portfolioHero">
        <div className="portfolioHero__name">{results.portfolio_name}</div>
        <div className="portfolioHero__desc">{results.portfolio_description}</div>

        <div className="sipStrip">
          {results.monthly_investment > 0 && (
            <div className="sipStrip__item">
              <div className="sipStrip__label">Monthly SIP</div>
              <div className="sipStrip__value">{fmt(results.monthly_investment)}</div>
            </div>
          )}
          {results.lump_sum > 0 && (
            <div className="sipStrip__item">
              <div className="sipStrip__label">One-time</div>
              <div className="sipStrip__value">{fmt(results.lump_sum)}</div>
            </div>
          )}
          <div className="sipStrip__item">
            <div className="sipStrip__label">Timeline</div>
            <div className="sipStrip__value">{years} yrs</div>
          </div>
          {results.risk_profile && (
            <div className="sipStrip__item">
              <div className="sipStrip__label">Risk profile</div>
              <div className="sipStrip__value">{results.risk_profile.label}</div>
            </div>
          )}
          <div className="sipStrip__item">
            <div className="sipStrip__label">Expected return</div>
            <div className="sipStrip__value">{results.expected_return?.toFixed(1)}% p.a.</div>
          </div>
        </div>
      </div>

      <div className="body">
        <WhatIf last={last} setLast={setLast} />

        {/* Asset mix */}
        <div className="card">
          <div className="card__title">Asset mix</div>
          <div className="mixBar" role="img" aria-label="Asset mix">
            {Object.entries(mix).filter(([, v]) => v > 0).map(([k, v]) => (
              <div key={k} className="mixBar__seg" style={{ width: `${v}%`, background: MIX_COLORS[k] }} />
            ))}
          </div>
          <div className="mixLegend">
            {Object.entries(mix).map(([k, v]) => (
              <span key={k} className="mixLegend__item">
                <span className="mixLegend__dot" style={{ background: MIX_COLORS[k] }} />
                {MIX_LABELS[k]} {Math.round(v)}%
              </span>
            ))}
          </div>
          {results.mix_reasons?.length > 0 && (
            <div className="mixReasons">
              <div className="mixReasons__title">Why this mix</div>
              <ul>
                {results.mix_reasons.map((r) => <li key={r}>{r}</li>)}
              </ul>
            </div>
          )}
        </div>

        {/* Projections */}
        <div className="card">
          <div className="card__title">What it could grow to in {years} years</div>
          <div className="projGrid">
            {SCENARIOS.map(([key, label]) => projections[key] && (
              <div key={key} className={`projBox ${key === "expected" ? "projBox--main" : ""}`}>
                <div className="projBox__label">{label}</div>
                <div className="projBox__value">{fmt(projections[key].corpus)}</div>
                <div className="projBox__sub">{projections[key].annual_return.toFixed(1)}% p.a.</div>
                <div className="projBox__sub">≈ {fmt(projections[key].corpus_today)} in today's money</div>
              </div>
            ))}
          </div>
          <div className="projNote">
            You invest {fmt(results.total_invested)} in total. "Today's money" assumes {results.inflation_assumption}% inflation.
            Projections use each fund category's long-run rolling returns, not guaranteed returns.
          </div>
          {results.target_amount && (
            <div className={`goalStatus goalStatus--${results.goal_status}`}>
              {results.goal_status === "on_track"
                ? `✅ On track for your ${target} target.`
                : `⚠️ Expected to fall short of ${target}. Increase your SIP by about ${fmt(results.shortfall_monthly)}/month or extend the timeline.`}
            </div>
          )}
        </div>

        {risk?.capacity != null && risk?.willingness != null && (
          <div className="card">
            <div className="card__title">Your risk profile: {risk.label} ({Math.round(risk.score)}/100)</div>
            <div className="projNote" style={{ marginTop: 0 }}>
              Ability to take risk {Math.round(risk.capacity)}/100 · Comfort with risk {Math.round(risk.willingness)}/100.{" "}
              {risk.limited_by === "capacity" && "Your finances set the limit, so the plan follows them rather than your appetite."}
              {risk.limited_by === "willingness" && "Your comfort level set the limit, so the plan won't take more risk than you're happy with."}
              {!risk.limited_by && "Both point the same way."}
            </div>
          </div>
        )}

        {results.warnings?.length > 0 && (
          <div className="warningBox">
            {results.warnings.map((w) => <div key={w} className="warningBox__item">⚠️ {w}</div>)}
          </div>
        )}

        <div className="sectionHeading">Your {funds.length} fund{funds.length !== 1 ? "s" : ""}</div>
        {funds.length === 0
          ? <div className="resultsEmpty">No funds could be selected right now. Please try again later.</div>
          : funds.map((fund) => <FundCard key={fund.scheme_code} fund={fund} />)
        }

        <div className="dataNote">
          Fund data as of {fmtDate(results.data_as_of)} from AMFI and mfapi.in. Funds are ranked within their SEBI
          category on 3- and 5-year returns, rolling-return consistency, volatility and worst fall, weighted for
          your risk profile. Methodology v{results.methodology_version}.
        </div>

        <Disclaimer />

        <div className="resultsActions">
          <SavePlan last={last} setLast={setLast} />
          {accountsEnabled && <Link className="btnOutline" to="/review">📊 Review the funds you already own</Link>}
          <button className="btnBlue" onClick={onBack}>← Adjust Profile</button>
        </div>
      </div>
    </div>
  );
}
