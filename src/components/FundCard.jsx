import { INVEST_URLS } from "../constants/investUrls";
import "../styles/FundCard.css";
import "../styles/shared.css";
import { getCategoryColor } from "../utils/colors";

export default function FundCard({ fund }) {
  const risk      = fund.risk_level || "";
  const color     = getCategoryColor(risk);
  const nav       = fund.nav != null ? "₹" + parseFloat(fund.nav).toFixed(2) : "—";
  const alloc     = fund.allocation_percentage != null ? Math.round(fund.allocation_percentage) + "%" : "—";
  const investAmt = fund.allocation_amount != null ? "₹" + Math.round(fund.allocation_amount).toLocaleString("en-IN") : "—";
  const r1        = fund.returns_1y ?? null;
  const r3        = fund.returns_3y ?? null;
  const r5        = fund.returns_5y ?? null;
  const investUrl = INVEST_URLS[fund.scheme_code] || "https://www.groww.in/mutual-funds";

  const RetVal = ({ period, val }) => val == null ? null : (
    <div className="returnBox">
      <div className="returnBox__period">{period}</div>
      <div className={`returnBox__value ${val >= 0 ? "returnBox__value--positive" : "returnBox__value--negative"}`}>
        {val >= 0 ? "↑" : "↓"}{parseFloat(val).toFixed(1)}%
      </div>
    </div>
  );

  return (
    <div className="fundCard">
      <div className="fundCard__top" style={{ background: color + "14", borderBottom: `1px solid ${color}22` }}>
        <div className="fundCard__badges">
          <span className="fundCard__pill" style={{ background: color }}>{fund.category || "Fund"}</span>
          <span className="fundCard__riskPill" style={{ color, borderColor: color + "44" }}>{risk || "—"} Risk</span>
        </div>
        <div className="fundCard__name">{fund.scheme_name || "Unknown Fund"}</div>
      </div>

      <div className="fundCard__body">
        <div className="metricsGrid">
          {[["Current NAV", nav], ["Allocation", alloc]].map(([lbl, val]) => (
            <div key={lbl} className="metricBox">
              <div className="metricBox__label">{lbl}</div>
              <div className="metricBox__value">{val}</div>
            </div>
          ))}
        </div>

        <div className="investBox">
          <span>💰</span>
          <span className="investBox__amount">Invest: {investAmt}</span>
        </div>

        {(r1 != null || r3 != null || r5 != null) && (
          <>
            <hr className="divider" />
            <div className="returnsTitle">Historical Returns</div>
            <div className="returnsGrid">
              <RetVal period="1Y" val={r1} />
              <RetVal period="3Y" val={r3} />
              <RetVal period="5Y" val={r5} />
            </div>
          </>
        )}

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

        <button className="investBtn" onClick={() => window.open(investUrl, "_blank")}>
          🔗 Invest Now
        </button>
      </div>
    </div>
  );
}