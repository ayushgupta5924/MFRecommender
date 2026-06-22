import { S } from "../styles/shared";
import { getCategoryColor } from "../utils/colors";

export default function FundCard({ fund }) {
  const risk      = fund.risk_level || "";
  const color     = getCategoryColor(risk);
  const nav       = fund.nav != null ? "₹" + parseFloat(fund.nav).toFixed(2) : "—";
  const alloc     = fund.allocation_percentage != null ? Math.round(fund.allocation_percentage) + "%" : "—";
  const investAmt = fund.allocation_amount != null ? "₹" + Math.round(fund.allocation_amount).toLocaleString("en-IN") : "—";
  const r1 = fund.returns_1y ?? null;
  const r3 = fund.returns_3y ?? null;
  const r5 = fund.returns_5y ?? null;

  const RetVal = ({ period, val }) => val == null ? null : (
    <div style={{ textAlign: "center", flex: 1, background: "#fafafa", borderRadius: 10, padding: "8px 4px", border: "1px solid #f0f0f0" }}>
      <div style={{ fontSize: 12, color: "#888" }}>{period}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color: val >= 0 ? "#2e7d32" : "#c62828", marginTop: 3 }}>
        {val >= 0 ? "↑" : "↓"}{parseFloat(val).toFixed(1)}%
      </div>
    </div>
  );

  return (
    <div style={{ background: "#fff", borderRadius: 16, marginBottom: 16, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.07)" }}>
      <div style={{ padding: "14px 18px", background: color + "14", borderBottom: `1px solid ${color}22` }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
          <span style={{ padding: "4px 12px", borderRadius: 20, fontSize: 12, fontWeight: 700, color: "#fff", background: color }}>{fund.category || "Fund"}</span>
          <span style={{ padding: "4px 12px", borderRadius: 20, fontSize: 12, fontWeight: 700, color: color, background: "#fff", border: `1px solid ${color}44` }}>{risk || "—"} Risk</span>
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, color: "#111", lineHeight: 1.4 }}>{fund.scheme_name || "Unknown Fund"}</div>
      </div>

      <div style={{ padding: "16px 18px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
          {[["Current NAV", nav], ["Allocation", alloc]].map(([lbl, val]) => (
            <div key={lbl} style={{ textAlign: "center", background: "#fafafa", borderRadius: 10, padding: "10px 8px", border: "1px solid #f0f0f0" }}>
              <div style={{ fontSize: 12, color: "#888" }}>{lbl}</div>
              <div style={{ fontSize: 16, fontWeight: 700, marginTop: 3 }}>{val}</div>
            </div>
          ))}
        </div>

        <div style={{ background: "#e8f5e9", borderRadius: 10, padding: "11px 14px", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 12 }}>
          <span>💰</span>
          <span style={{ fontSize: 16, fontWeight: 700, color: "#2e7d32" }}>Invest: {investAmt}</span>
        </div>

        {(r1 != null || r3 != null || r5 != null) && (
          <>
            <hr style={S.divider} />
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8, color: "#444" }}>Historical Returns</div>
            <div style={{ display: "flex", gap: 8 }}>
              <RetVal period="1Y" val={r1} />
              <RetVal period="3Y" val={r3} />
              <RetVal period="5Y" val={r5} />
            </div>
          </>
        )}

        {fund.reason && (
          <>
            <hr style={S.divider} />
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <span>💡</span>
              <span style={{ fontWeight: 700, fontSize: 13, color: "#444" }}>Why this fund?</span>
            </div>
            <p style={{ fontSize: 13, color: "#777", margin: 0, lineHeight: 1.6 }}>{fund.reason}</p>
          </>
        )}

        <button onClick={() => window.open(fund.investment_url || "#", "_blank")}
          style={{ ...S.btnBlue, marginTop: 14, borderRadius: 10, padding: "12px", fontSize: 14 }}>
          🔗 Invest Now
        </button>
      </div>
    </div>
  );
}