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

const crore = (n) => `₹${Math.round(n).toLocaleString("en-IN")} cr`;

// What we look at beyond past returns: costs, size, the index, the portfolio and the people running it.
function FundFacts({ fund: f }) {
  const rows = [];
  if (f.expense_ratio != null) {
    rows.push(["Expense ratio", `${f.expense_ratio.toFixed(2)}% a year`,
      f.category_median_expense_ratio != null ? `category ${f.category_median_expense_ratio.toFixed(2)}%` : null]);
  }
  if (f.aum_cr != null) rows.push(["Fund size", crore(f.aum_cr), null]);
  if (f.benchmark && f.beat_rate != null) {
    rows.push([`vs ${f.benchmark}`, `beat it in ${Math.round(f.beat_rate)}% of 3-yr periods`,
      f.down_capture != null ? `took ${Math.round(f.down_capture)}% of its falls` : null]);
  }
  if (f.stocks) {
    rows.push(["Portfolio", `${f.stocks} stocks${f.top10_pct != null ? ` · top 10 = ${Math.round(f.top10_pct)}%` : ""}`,
      f.cash_pct != null ? `cash ${f.cash_pct.toFixed(1)}%${f.portfolio_date ? `, ${fmtDate(f.portfolio_date)}` : ""}` : null]);
  }
  if (f.managers?.length) {
    rows.push(["Fund manager", f.managers.join(", "),
      f.manager_changed ? `new since ${fmtDate(f.manager_since)}` : null]);
  }
  if (!rows.length) return null;
  return (
    <>
      <hr className="divider" />
      <div className="returnsTitle">Beyond past returns</div>
      <div className="factList">
        {rows.map(([label, value, note]) => (
          <div key={label} className="factRow">
            <span className="factRow__label">{label}</span>
            <span className="factRow__value">{value}{note && <small> · {note}</small>}</span>
          </div>
        ))}
      </div>
      {f.size_note && <div className="factWarn">⚠️ {f.size_note}</div>}
    </>
  );
}

export default function FundCard({ fund }) {
  const [showAlternatives, setShowAlternatives] = useState(false);
  const risk  = fund.risk_level || "";
  const color = getCategoryColor(risk);
  const nav   = fund.nav != null ? "₹" + parseFloat(fund.nav).toFixed(2) : "—";
  const alloc = fund.allocation_percentage != null ? Math.round(fund.allocation_percentage) + "%" : "—";
  const rupees = (n) => "₹" + Math.round(n || 0).toLocaleString("en-IN");
  const investUrl = fund.investment_url || "https://www.mfcentral.com/";
  const alternatives = fund.alternatives || [];

  return (
    <div className="fundCard">
      <div className="fundCard__top" style={{ background: color + "14", borderBottom: `1px solid ${color}22` }}>
        <div className="fundCard__badges">
          <span className="fundCard__pill" style={{ background: color }}>{fund.category || "Fund"}</span>
          <span className="fundCard__riskPill" style={{ color, borderColor: color + "44" }}>{risk || "—"} Risk</span>
          {fund.rating_label && (
            <span className={`statusChip statusChip--${fund.rating_status}`}
              title="Which quarter of its whole category it ranks in, as the portfolio review rates it.">
              {fund.rating_label}
            </span>
          )}
          {fund.rank != null && (
            <span className="fundCard__rankPill" title="Its rank among the funds we pick from for your risk profile.">
              #{fund.rank} of {fund.rank_of}
            </span>
          )}
          {fund.already_held && <span className="fundCard__heldPill">You hold this</span>}
          {fund.lock_in_years > 0 && <span className="fundCard__lockPill">🔒 {fund.lock_in_years}-yr lock-in</span>}
        </div>
        <div className="fundCard__name">{fund.scheme_name || "Unknown Fund"}</div>
        <div className="fundCard__amc">
          {fund.amc} · Direct Plan · Growth
          {fund.info_url && (
            <> · <a className="fundCard__infoLink" href={fund.info_url} target="_blank" rel="noopener noreferrer">Fund details ↗</a></>
          )}
        </div>
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

        <FundFacts fund={fund} />

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
                  <div className="alternatives__name">
                    {a.info_url ? <a href={a.info_url} target="_blank" rel="noopener noreferrer">{a.scheme_name}</a> : a.scheme_name}
                  </div>
                  <div className="alternatives__amc">{a.amc}</div>
                </div>
                <div className="alternatives__ret">
                  {a.returns_5y != null ? `5Y ${pct(a.returns_5y)}` : `3Y ${pct(a.returns_3y)}`}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="howToInvest">
          <div className="howToInvest__title">How to invest</div>
          <div className="fundCard__note">
            Buy the <strong>Direct – Growth</strong> option on the fund house's own website,{" "}
            <a href={investUrl} target="_blank" rel="noopener noreferrer">MF Central</a> (run by the registrars CAMS and
            KFintech), or any platform that offers Direct plans.
            {fund.isin && <> ISIN: <code>{fund.isin}</code>.</>}
          </div>
          <div className="fundCard__note">
            We earn nothing from where you invest. Read the scheme documents before investing.
            {fund.info_url && <> &ldquo;Fund details&rdquo; opens the fund&apos;s page on Zerodha Coin, for information only.</>}
          </div>
        </div>
      </div>
    </div>
  );
}
