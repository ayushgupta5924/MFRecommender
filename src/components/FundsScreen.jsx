import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getCategoryFunds, getFundCategories, searchFunds } from "../api";
import { STATUS_LABEL } from "../constants/ratings";
import "../styles/FundPage.css";
import { fmtDate } from "../utils/format";
import { usePageMeta } from "../utils/meta";
import AppBar from "./AppBar";
import Disclaimer from "./Disclaimer";

const SLEEVES = [["equity", "Equity"], ["hybrid", "Hybrid"], ["debt", "Debt"]];
const pctF = (v) => (v == null ? "—" : `${v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(1)}%`);

function FundSearch() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);

  useEffect(() => {
    if (q.trim().length < 2) return undefined;
    let live = true;
    const t = setTimeout(() => {
      searchFunds(q.trim()).then((h) => live && setHits(h)).catch(() => live && setHits([]));
    }, 250);
    return () => { live = false; clearTimeout(t); };
  }, [q]);
  const shown = q.trim().length < 2 ? [] : hits;

  return (
    <div className="fundSearch">
      <Search size={18} className="fundSearch__icon" />
      <input className="fieldInput fundSearch__input" value={q} onChange={(e) => setQ(e.target.value)}
        placeholder="Search any mutual fund, e.g. Parag Parikh Flexi Cap" aria-label="Search funds"
        onKeyDown={(e) => { if (e.key === "Enter" && shown[0]) navigate(`/fund/${shown[0].code}`); }} />
      {shown.length > 0 && (
        <div className="fundSearch__hits">
          {shown.map((h) => (
            <Link key={h.code} to={`/fund/${h.code}`} className="fundHit">
              <span className="fundHit__name">{h.name}</span>
              <span className="fundHit__meta">{h.amc} · {h.plan} {h.option} · {h.category}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function FundsScreen() {
  const [params, setParams] = useSearchParams();
  const [cats, setCats] = useState(null);
  const [list, setList] = useState(null);
  const [error, setError] = useState("");
  const current = params.get("c") || "flexi_cap";

  usePageMeta("Mutual fund rankings by category",
    "Every Direct-Growth mutual fund in India ranked against its category on returns, consistency, falls, costs and size, rebuilt every night.");

  useEffect(() => {
    getFundCategories().then(setCats).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    let live = true;
    getCategoryFunds(current).then((l) => live && setList(l)).catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [current]);

  return (
    <div className="page">
      <AppBar />
      <div className="body fundsPage">
        <div className="eyebrow">Fund research</div>
        <h1 className="fundsPage__title">Every fund, ranked against its category</h1>
        <p className="fundsPage__sub">
          Look up any mutual fund, or browse a category. Ranks use returns, consistency, falls, costs and fund size, and
          are rebuilt every night from AMFI data.
        </p>
        <FundSearch />
        {error && <div className="errorText">{error}</div>}

        {cats && SLEEVES.map(([sleeve, label]) => (
          <div key={sleeve} className="catGroup">
            <span className="catGroup__label">{label}</span>
            <div className="catGroup__chips">
              {cats.categories.filter((c) => c.sleeve === sleeve).map((c) => (
                <button key={c.key} className={`chip chip--btn ${c.key === current ? "chip--on" : ""}`}
                  onClick={() => setParams({ c: c.key }, { replace: true })}>
                  {c.label} <small>{c.count}</small>
                </button>
              ))}
            </div>
          </div>
        ))}

        {!list && !error && <div className="pageLoading">Loading rankings… (the server can take up to a minute to wake up)</div>}
        {list && (
          <div className="card rankTable">
            <div className="rankTable__head">
              <div>
                <div className="card__title" style={{ marginBottom: 4 }}>{list.label}</div>
                <div className="mutedText">{list.role} {list.benchmark && `Index: ${list.benchmark}.`}</div>
              </div>
              <span className="chip chip--muted">{list.risk_level} risk</span>
            </div>
            <div className="rankRow rankRow--head">
              <span>#</span><span>Fund</span><span>Rating</span><span>3 yr</span><span className="hideSm">5 yr</span>
              <span className="hideSm">Cost</span>
            </div>
            {list.funds.map((f) => (
              <Link key={f.code} to={`/fund/${f.code}`} className="rankRow">
                <span className="rankRow__n num">{f.rank}</span>
                <span className="rankRow__name">{f.name}<small>{f.amc}</small></span>
                <span><span className={`statusChip statusChip--${f.status}`}>{STATUS_LABEL[f.status]}</span></span>
                <span className={`num ${f.cagr_3y >= 0 ? "pos" : "neg"}`}>{pctF(f.cagr_3y)}</span>
                <span className={`num hideSm ${f.cagr_5y >= 0 ? "pos" : "neg"}`}>{pctF(f.cagr_5y)}</span>
                <span className="num hideSm">{f.ter != null ? `${f.ter.toFixed(2)}%` : "—"}</span>
              </Link>
            ))}
            <div className="dataNote" style={{ margin: "14px 0 0" }}>
              Rankings as of {fmtDate(list.as_of)}. Funds need {list.sleeve === "debt" ? "1–2" : "3"}+ years of history
              to be ranked. General information on past data, not a recommendation to buy or sell any fund.
            </div>
          </div>
        )}
        <Disclaimer />
      </div>
    </div>
  );
}
