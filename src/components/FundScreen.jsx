import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, Layers, Trophy, TriangleAlert, Users } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getFund } from "../api";
import { STATUS_LABEL } from "../constants/ratings";
import "../styles/FundPage.css";
import { fmtDate } from "../utils/format";
import { usePageMeta } from "../utils/meta";
import AppBar from "./AppBar";
import Disclaimer from "./Disclaimer";
import LineChart from "./LineChart";

const PERIODS = [["1Y", 1], ["3Y", 3], ["5Y", 5], ["All", null]];
const pctF = (v, digits = 1) => (v == null ? "—" : `${v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(digits)}%`);
const rupee = (v) => `₹${v.toLocaleString("en-IN", { maximumFractionDigits: v < 100 ? 2 : 0 })}`;
const crore = (v) => (v == null ? "—" : `₹${Math.round(v).toLocaleString("en-IN")} cr`);
const tone = (v) => (v == null ? "" : v >= 0 ? "pos" : "neg");

function Stat({ label, value, sub, className = "" }) {
  return (
    <div className="fpStat">
      <span>{label}</span>
      <b className={`num ${className}`}>{value}</b>
      {sub && <small>{sub}</small>}
    </div>
  );
}

function NavChart({ chart }) {
  const [period, setPeriod] = useState(3);
  const points = useMemo(() => {
    const all = chart.map(([date, value]) => ({ date, value }));
    if (!period || !all.length) return all;
    const from = new Date(all[all.length - 1].date);
    from.setFullYear(from.getFullYear() - period);
    const cut = from.toISOString().slice(0, 10);
    return all.filter((p) => p.date >= cut);
  }, [chart, period]);
  const change = points.length > 1 ? points[points.length - 1].value / points[0].value - 1 : null;

  return (
    <div className="card">
      <div className="fpChartHead">
        <div>
          <div className="card__title" style={{ marginBottom: 2 }}>NAV</div>
          {change != null && (
            <div className={`fpChange ${tone(change)}`}>
              {change >= 0 ? "+" : ""}{pctF(change)} <span>over {period ? `${period} yr` : "the fund's life"}</span>
            </div>
          )}
        </div>
        <div className="segmented" role="tablist" aria-label="Period">
          {PERIODS.map(([label, years]) => (
            <button key={label} role="tab" aria-selected={period === years}
              className={`segmented__btn ${period === years ? "segmented__btn--on" : ""}`} onClick={() => setPeriod(years)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <LineChart points={points} label="NAV over time" fmtY={(v) => `₹${v.toFixed(v < 100 ? 1 : 0)}`}
        fmtTip={(v) => `NAV ₹${v.toFixed(2)}`} />
    </div>
  );
}

function RankTrend({ history, rating }) {
  if (!history.length) return null;
  const points = history.map((h) => ({ date: h.date, value: h.rank, rank_of: h.rank_of }));
  const worst = Math.max(...history.map((h) => h.rank_of));
  return (
    <div className="card">
      <div className="card__title"><Trophy size={18} /> Rank in its category</div>
      {history.length < 4 ? (
        <div className="fpEmptyTrend">
          <div className="fpRankBig num">#{rating.rank}<span> of {rating.rank_of}</span></div>
          <p className="mutedText">
            We started recording weekly ranks in October 2026; the trend chart fills in from here, one point a week,
            up to two years.
          </p>
        </div>
      ) : (
        <LineChart points={points} invert yDomain={[1, worst]} label="Rank over time"
          fmtY={(v) => `#${Math.round(v)}`} fmtTip={(v, p) => `#${v} of ${p.rank_of}`} />
      )}
    </div>
  );
}

export default function FundScreen() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [fund, setFund] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    getFund(code).then((f) => live && setFund(f)).catch((e) => live && setError(e.message));
    return () => { live = false; setFund(null); setError(""); };
  }, [code]);

  usePageMeta(fund ? `${fund.name}: rating, returns and rank` : "Fund",
    fund ? `${fund.name} (${fund.bucket_label || fund.category}): how it ranks against its category, returns, risk, costs and holdings.` : undefined);

  const r = fund?.rating || {};
  const m = r.metrics || {};
  const cat = r.category || {};
  const ret = fund?.returns || {};

  return (
    <div className="page">
      <AppBar title="Fund" onBack={() => navigate(-1)} />
      <div className="body fundPage">
        {error && <div className="errorText">{error}</div>}
        {!fund && !error && <div className="pageLoading">Loading fund… (the server can take up to a minute to wake up)</div>}

        {fund && (
          <>
            <header className="fpHead">
              <div className="fpHead__chips">
                {fund.bucket_label && <Link className="chip" to={`/funds?c=${fund.bucket}`}>{fund.bucket_label}</Link>}
                <span className="chip chip--muted">{fund.plan} · {fund.option}</span>
                {fund.risk_level && <span className="chip chip--muted">{fund.risk_level} risk</span>}
              </div>
              <h1 className="fpHead__name">{fund.name}</h1>
              <div className="fpHead__amc">{fund.amc}</div>
              <div className="fpHead__row">
                {fund.nav && (
                  <div className="fpNav">
                    <span className="num">{rupee(fund.nav.value)}</span>
                    <small>NAV on {fmtDate(fund.nav.date)}</small>
                  </div>
                )}
                <div className="fpRating">
                  <span className={`statusChip statusChip--${r.status}`}>{STATUS_LABEL[r.status]}</span>
                  {r.rank && <span className="fpRating__rank">#{r.rank} of {r.rank_of} in {fund.bucket_label}</span>}
                </div>
              </div>
              <p className="fpHead__reason">{r.reason}</p>
            </header>

            {fund.direct_growth_twin && (
              <div className="warningBox">
                <div className="warningBox__title"><TriangleAlert size={15} className="ico" /> This is a {fund.plan} {fund.option} plan</div>
                <div className="warningBox__item">
                  It's rated through its Direct-Growth version,{" "}
                  <Link to={`/fund/${fund.direct_growth_twin.code}`}>{fund.direct_growth_twin.name}</Link>
                  {fund.plan === "Regular" && ", which costs less every year because it pays no distributor commission"}.
                </div>
              </div>
            )}

            {fund.chart.length > 1 && <NavChart chart={fund.chart} />}

            <div className="card">
              <div className="card__title">Returns (a year)</div>
              <div className="fpStats">
                {[1, 3, 5, 10].map((y) => (
                  <Stat key={y} label={`${y} yr`} value={pctF(ret[`cagr_${y}y`])} className={tone(ret[`cagr_${y}y`])}
                    sub={cat[`cagr_${y}y`] != null ? `Category ${pctF(cat[`cagr_${y}y`])}` : null} />
                ))}
              </div>
              <div className="mutedText fpNote">Annualised, from daily NAVs. Category figures are the median of every
                fund we rank in {fund.bucket_label || "its category"}.</div>
            </div>

            {r.metrics && (
              <div className="card">
                <div className="card__title">Risk, costs and size</div>
                <div className="fpStats">
                  <Stat label="Worst fall" value={pctF(m.max_drawdown, 0)} sub={cat.max_drawdown != null ? `Category ${pctF(cat.max_drawdown, 0)}` : null} />
                  <Stat label="Volatility" value={pctF(m.volatility)} />
                  <Stat label="Expense ratio" value={m.ter != null ? `${m.ter.toFixed(2)}%` : "—"} sub={cat.ter != null ? `Category ${cat.ter.toFixed(2)}%` : null} />
                  <Stat label="Fund size" value={crore(m.aum_cr)} />
                  {m.rolling_median != null && <Stat label="Typical rolling return" value={pctF(m.rolling_median)} />}
                  {m.excess_return != null && <Stat label={`vs ${r.benchmark || "index"}`} value={pctF(m.excess_return)} className={tone(m.excess_return)} sub="a year, after costs" />}
                </div>
                {r.size_note && <div className="factWarn" style={{ marginTop: 12 }}><TriangleAlert size={14} className="ico" /> {r.size_note}</div>}
              </div>
            )}

            {(m.managers?.length > 0 || fund.top_holdings.length > 0) && (
              <div className="fpTwo">
                {m.managers?.length > 0 && (
                  <div className="card">
                    <div className="card__title"><Users size={18} /> Fund managers</div>
                    <ul className="fpList">{m.managers.map((n) => <li key={n}>{n}</li>)}</ul>
                    {m.manager_changed && <div className="factWarn"><TriangleAlert size={14} className="ico" /> The management team changed recently, so past returns say less about the future.</div>}
                  </div>
                )}
                {fund.top_holdings.length > 0 && (
                  <div className="card">
                    <div className="card__title"><Layers size={18} /> Top holdings</div>
                    {fund.top_holdings.map((h) => (
                      <div key={h.company} className="fpHolding">
                        <span>{h.company}</span>
                        <span className="fpHolding__bar"><i style={{ width: `${Math.min(h.pct * 8, 100)}%` }} /></span>
                        <b className="num">{h.pct.toFixed(1)}%</b>
                      </div>
                    ))}
                    {fund.portfolio_date && <div className="mutedText fpNote">As disclosed on {fmtDate(fund.portfolio_date)}.</div>}
                  </div>
                )}
              </div>
            )}

            <RankTrend history={fund.rank_history} rating={r} />

            {fund.peers.length > 0 && (
              <div className="card">
                <div className="card__title">Top-ranked {fund.bucket_label} funds</div>
                {fund.peers.map((p) => (
                  <Link key={p.code} to={`/fund/${p.code}`} className={`fpPeer ${p.code === fund.code ? "fpPeer--me" : ""}`}>
                    <span className="fpPeer__rank num">#{p.rank}</span>
                    <span className="fpPeer__name">{p.name}<small>{p.amc}</small></span>
                    <span className="fpPeer__ret num">{pctF(p.cagr_3y)}<small>3 yr</small></span>
                  </Link>
                ))}
                <Link className="linkBtn fpMore" to={`/funds?c=${fund.bucket}`}>See all {fund.bucket_label} funds →</Link>
              </div>
            )}

            <div className="fpLinks">
              {fund.info_url && (
                <a className="btnOutline" href={fund.info_url} target="_blank" rel="noopener noreferrer">
                  Fund factsheet on Zerodha Coin <ArrowUpRight size={16} />
                </a>
              )}
              <Link className="btnOutline" to="/review">Check how your own funds rank</Link>
            </div>
            <div className="dataNote">
              Rankings as of {fmtDate(fund.as_of)}, from AMFI NAVs, rebuilt every night. A rating compares the fund with its
              category on past data; it is general information, not a recommendation to buy or sell this fund.
              ISIN {fund.isin || "—"}, AMFI code {fund.code}.
            </div>
            <Disclaimer />
          </>
        )}
      </div>
    </div>
  );
}
