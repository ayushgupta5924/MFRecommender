import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { savePlan } from "../api";
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
  const { user } = useAuth();
  const [state, setState] = useState({ saving: false, error: "" });

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

export default function ResultsScreen() {
  const navigate = useNavigate();
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
          <div className="sipStrip__item">
            <div className="sipStrip__label">Monthly SIP</div>
            <div className="sipStrip__value">{fmt(results.monthly_investment)}</div>
          </div>
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
          <Link className="btnOutline" to="/review">📊 Review the funds you already own</Link>
          <button className="btnBlue" onClick={onBack}>← Adjust Profile</button>
        </div>
      </div>
    </div>
  );
}
