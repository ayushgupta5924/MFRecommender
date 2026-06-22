import "../styles/FundCard.css";
import "../styles/shared.css";
import Disclaimer from "./Disclaimer";
import FundCard from "./FundCard";

const AFFILIATE_CODE = "YOUR_GROWW_AFFILIATE_CODE";

export default function ResultsScreen({ onBack, results, budget }) {
  const recs = results?.recommendations || (Array.isArray(results) ? results : []);

  return (
    <div className="page">
      <div className="appBar">
        <button className="backBtn" onClick={onBack}>←</button>
        <span className="appBar__title">Your Recommendations</span>
      </div>

      <div className="resultsHero">
        <div className="resultsHero__icon">✅</div>
        <div className="resultsHero__amount">₹{Math.round(budget).toLocaleString("en-IN")}</div>
        <div className="resultsHero__count">{recs.length} Fund{recs.length !== 1 ? "s" : ""} Found</div>
      </div>

      <div className="body">
        <Disclaimer />

        {recs.length === 0
          ? <div className="resultsEmpty">No funds found. Check backend logs.</div>
          : recs.map((fund, i) => <FundCard key={i} fund={fund} />)
        }

        <div className="poweredBy">
          <span>Investments powered by</span>
          <a
            href={`https://groww.in?ref=${AFFILIATE_CODE}`}
            target="_blank"
            rel="noreferrer"
            className="poweredBy__link">
            📈 Groww
          </a>
        </div>

        <button className="btnBlue" onClick={onBack}>← Adjust Profile</button>
      </div>
    </div>
  );
}