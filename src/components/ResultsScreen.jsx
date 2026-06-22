import { S } from "../styles/shared";
import FundCard from "./FundCard";

export default function ResultsScreen({ onBack, results, budget }) {
  const recs = results?.recommendations || (Array.isArray(results) ? results : []);

  return (
    <div style={S.page}>
      <div style={S.appBar}>
        <button onClick={onBack} style={S.backBtn}>←</button>
        <span style={{ fontSize: 17, fontWeight: 700, color: "#fff" }}>Your Recommendations</span>
      </div>

      <div style={{ background: "linear-gradient(180deg,#1976d2,#1e88e5)", padding: "36px 24px 30px", textAlign: "center", color: "#fff" }}>
        <div style={{ fontSize: 50 }}>✅</div>
        <div style={{ fontSize: 36, fontWeight: 800, marginTop: 10 }}>₹{Math.round(budget).toLocaleString("en-IN")}</div>
        <div style={{ fontSize: 15, color: "rgba(255,255,255,0.85)", marginTop: 6 }}>
          {recs.length} Fund{recs.length !== 1 ? "s" : ""} Recommended
        </div>
      </div>

      <div style={{ maxWidth: 760, margin: "0 auto", padding: "24px 20px 48px" }}>
        {recs.length === 0
          ? <div style={{ textAlign: "center", color: "#888", fontSize: 15, marginTop: 40 }}>No recommendations returned. Check backend logs.</div>
          : recs.map((fund, i) => <FundCard key={i} fund={fund} />)
        }
        <button onClick={onBack} style={{ ...S.btnBlue, marginTop: 8 }}>← Adjust Profile</button>
      </div>
    </div>
  );
}