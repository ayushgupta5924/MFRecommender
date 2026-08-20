import "../styles/FundCard.css";
import "../styles/ResultsScreen.css";
import "../styles/shared.css";
import Disclaimer from "./Disclaimer";
import FundCard from "./FundCard";

const AFFILIATE_CODE = "YOUR_GROWW_AFFILIATE_CODE";

function fmt(n) {
  if (!n) return "—";
  if (n >= 10000000) return "₹" + (n / 10000000).toFixed(1) + " Cr";
  if (n >= 100000)   return "₹" + (n / 100000).toFixed(1) + " L";
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

export default function ResultsScreen({ onBack, results, budget }) {
  // Handle both old flat array and new portfolio response
  const isPortfolio = results && results.portfolio_name;
  const recs = isPortfolio
    ? results.funds
    : (results?.recommendations || (Array.isArray(results) ? results : []));

  return (
    <div className="page">
      <div className="appBar">
        <button className="backBtn" onClick={onBack}>←</button>
        <span className="appBar__title">Your Portfolio</span>
      </div>

      {/* Portfolio hero */}
      {isPortfolio ? (
        <div className="portfolioHero">
          <div className="portfolioHero__name">{results.portfolio_name}</div>
          <div className="portfolioHero__desc">{results.portfolio_description}</div>

          {/* SIP math strip */}
          <div className="sipStrip">
            {results.monthly_sip_required && (
              <div className="sipStrip__item">
                <div className="sipStrip__label">Monthly SIP</div>
                <div className="sipStrip__value">{fmt(results.monthly_sip_required)}</div>
              </div>
            )}
            {results.target_amount && (
              <div className="sipStrip__item">
                <div className="sipStrip__label">Target Corpus</div>
                <div className="sipStrip__value">{fmt(results.target_amount)}</div>
              </div>
            )}
            {results.target_years && (
              <div className="sipStrip__item">
                <div className="sipStrip__label">Timeline</div>
                <div className="sipStrip__value">{results.target_years} yrs</div>
              </div>
            )}
            <div className="sipStrip__item">
              <div className="sipStrip__label">Expected Return</div>
              <div className="sipStrip__value">{results.expected_return?.toFixed(0)}% p.a.</div>
            </div>
          </div>
        </div>
      ) : (
        <div className="resultsHero">
          <div className="resultsHero__icon">✅</div>
          <div className="resultsHero__amount">{fmt(budget)}</div>
          <div className="resultsHero__count">{recs.length} Fund{recs.length !== 1 ? "s" : ""} Found</div>
        </div>
      )}

      <div className="body">
        <Disclaimer />

        {recs.length === 0
          ? <div className="resultsEmpty">No funds found. Check backend logs.</div>
          : recs.map((fund, i) => <FundCard key={i} fund={fund} />)
        }

        <div className="poweredBy">
          <span>Investments powered by</span>
          <a href={`https://groww.in?ref=${AFFILIATE_CODE}`} target="_blank"
            rel="noreferrer" className="poweredBy__link">📈 Groww</a>
        </div>

        <button className="btnBlue" onClick={onBack}>← Adjust Profile</button>
      </div>
    </div>
  );
}