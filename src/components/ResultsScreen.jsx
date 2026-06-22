import "../styles/FundCard.css";
import "../styles/shared.css";
import FundCard from "./FundCard";

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
        <div className="resultsHero__count">{recs.length} Fund{recs.length !== 1 ? "s" : ""} Recommended</div>
      </div>

      <div className="body">
        {recs.length === 0
          ? <div className="resultsEmpty">No recommendations returned. Check backend logs.</div>
          : recs.map((fund, i) => <FundCard key={i} fund={fund} />)
        }
        <button className="btnBlue" onClick={onBack}>← Adjust Profile</button>
      </div>
    </div>
  );
}