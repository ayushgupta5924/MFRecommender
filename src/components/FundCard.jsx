import { useState } from "react";
import "../styles/FundCard.css";
import "../styles/shared.css";
import { getCategoryColor } from "../utils/colors";
import { fmtDate, pct } from "../utils/format";

function RetVal({ period, val, median }) {
  return (
    <div className="returnBox">
      <div className="returnBox__period">{period}</div>
      <div className={`returnBox__value ${val == null ? "" : val >= 0 ? "returnBox__value--positive" : "returnBox__value--negative"}`}>
        {val == null ? "—" : pct(val)}
      </div>
      {median != null && <div className="returnBox__median">Category {pct(median)}</div>}
    </div>
  );
}

export default function FundCard({ fund }) {
  const [showAlternatives, setShowAlternatives] = useState(false);
  const risk  = fund.risk_level || "";
  const color = getCategoryColor(risk);
  const nav   = fund.nav != null ? "₹" + parseFloat(fund.nav).toFixed(2) : "—";
  const alloc = fund.allocation_percentage != null ? Math.round(fund.allocation_percentage) + "%" : "—";
  const rupees = (n) => "₹" + Math.round(n || 0).toLocaleString("en-IN");
  const investUrl = fund.investment_url || `https://groww.in/search?q=${encodeURIComponent(fund.scheme_name || "mutual fund")}`;
  const alternatives = fund.alternatives || [];

  return (
    <div className="fundCard">
      <div className="fundCard__top" style={{ background: color + "14", borderBottom: `1px solid ${color}22` }}>
        <div className="fundCard__badges">
          <span className="fundCard__pill" style={{ background: color }}>{fund.category || "Fund"}</span>
          <span className="fundCard__riskPill" style={{ color, borderColor: color + "44" }}>{risk || "—"} Risk</span>
          {fund.rank != null && (
            <span className="fundCard__rankPill">#{fund.rank} of {fund.rank_of}</span>
          )}
          {fund.lock_in_years > 0 && <span className="fundCard__lockPill">🔒 {fund.lock_in_years}-yr lock-in</span>}
        </div>
        <div className="fundCard__name">{fund.scheme_name || "Unknown Fund"}</div>
        <div className="fundCard__amc">{fund.amc} · Direct Plan · Growth</div>
      </div>

      <div className="fundCard__body">
        <div className="investBox">
          <span>💰</span>
          <span className="investBox__amount">
            {fund.monthly_sip_amount > 0 && `Monthly SIP: ${rupees(fund.monthly_sip_amount)}`}
            {fund.monthly_sip_amount > 0 && fund.lump_sum_amount > 0 && " · "}
            {fund.lump_sum_amount > 0 && `One-time: ${rupees(fund.lump_sum_amount)}`}
          </span>
          <span className="investBox__share">{alloc} of plan</span>
        </div>

        <hr className="divider" />
        <div className="returnsTitle">Returns (annualised)</div>
        <div className="returnsGrid">
          <RetVal period="1Y" val={fund.returns_1y} />
          <RetVal period="3Y" val={fund.returns_3y} median={fund.category_median_3y} />
          <RetVal period="5Y" val={fund.returns_5y} median={fund.category_median_5y} />
        </div>

        <div className="metricsGrid metricsGrid--three">
          <div className="metricBox">
            <div className="metricBox__label">NAV ({fmtDate(fund.nav_date)})</div>
            <div className="metricBox__value">{nav}</div>
          </div>
          <div className="metricBox">
            <div className="metricBox__label">Volatility</div>
            <div className="metricBox__value">{pct(fund.volatility)}</div>
          </div>
          <div className="metricBox">
            <div className="metricBox__label">Worst fall (5y)</div>
            <div className="metricBox__value">{pct(fund.max_drawdown)}</div>
          </div>
        </div>

        {fund.reason && (
          <>
            <hr className="divider" />
            <div className="whyRow">
              <span>💡</span>
              <span className="whyTitle">Why this fund?</span>
            </div>
            <p className="whyText">{fund.reason}</p>
          </>
        )}

        {alternatives.length > 0 && (
          <div className="alternatives">
            <button type="button" className="alternatives__toggle" onClick={() => setShowAlternatives((v) => !v)}>
              {showAlternatives ? "▾" : "▸"} {alternatives.length} close alternative{alternatives.length > 1 ? "s" : ""}
            </button>
            {showAlternatives && alternatives.map((a) => (
              <div key={a.scheme_code} className="alternatives__row">
                <div>
                  <div className="alternatives__name">{a.scheme_name}</div>
                  <div className="alternatives__amc">{a.amc}</div>
                </div>
                <div className="alternatives__ret">
                  {a.returns_5y != null ? `5Y ${pct(a.returns_5y)}` : `3Y ${pct(a.returns_3y)}`}
                </div>
              </div>
            ))}
          </div>
        )}

        <a className="investBtn" href={investUrl} target="_blank" rel="noopener noreferrer">
          📈 View on Groww
        </a>
        <div className="fundCard__note">Choose the <strong>Direct – Growth</strong> option. Read the scheme documents before investing.</div>
      </div>
    </div>
  );
}
