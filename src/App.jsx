import { useState } from "react";
import { getRecommendations } from "./api";

const GOALS = [
  { value: "retirement", label: "Retirement" },
  { value: "wealth_creation", label: "Wealth Creation" },
  { value: "education", label: "Education" },
  { value: "tax_saving", label: "Tax Saving" },
  { value: "short_term", label: "Short Term" },
];

const RISK_OPTIONS = [
  { value: "low",      label: "Low",      desc: "Stable returns, minimal risk",   color: "#388e3c", bg: "rgba(56,142,60,0.08)",   icon: "🛡️" },
  { value: "moderate", label: "Moderate", desc: "Balanced growth & stability",    color: "#f57c00", bg: "rgba(245,124,0,0.08)",   icon: "⚖️" },
  { value: "high",     label: "High",     desc: "Maximum growth potential",       color: "#d32f2f", bg: "rgba(211,47,47,0.08)",   icon: "📈" },
];

function getCategoryColor(risk) {
  const r = (risk || "").toLowerCase();
  if (r === "high") return "#c62828";
  if (r === "moderate") return "#e65100";
  return "#2e7d32";
}

// ─── Shared styles ────────────────────────────────────────────────────────────
const S = {
  page:        { minHeight: "100vh", background: "#f0f2f5" },
  appBar:      { background: "#1976d2", padding: "0 24px", display: "flex", alignItems: "center", gap: 14, height: 56, position: "sticky", top: 0, zIndex: 10 },
  backBtn:     { background: "none", border: "none", color: "#fff", fontSize: 22, cursor: "pointer", lineHeight: 1, padding: 0 },
  hero:        { background: "linear-gradient(180deg,#1976d2,#1e88e5)", padding: "32px 24px 28px", textAlign: "center", color: "#fff" },
  body:        { maxWidth: 760, margin: "0 auto", padding: "24px 20px 48px" },
  card:        { background: "#fff", borderRadius: 16, padding: "20px 24px", marginBottom: 16, boxShadow: "0 1px 4px rgba(0,0,0,0.08)" },
  sectionHead: { fontSize: 17, fontWeight: 700, color: "#111", marginBottom: 16 },
  label:       { fontSize: 13, color: "#888", marginBottom: 4, display: "block" },
  inputWrap:   { position: "relative", marginBottom: 14 },
  input:       { width: "100%", padding: "13px 14px 13px 40px", border: "1.5px solid #e0e0e0", borderRadius: 12, background: "#fafafa", fontSize: 15, outline: "none", color: "#222", boxSizing: "border-box", transition: "border 0.15s" },
  iconLeft:    { position: "absolute", left: 13, top: "50%", transform: "translateY(-50%)", fontSize: 17, color: "#1976d2", pointerEvents: "none" },
  btnBlue:     { background: "#1976d2", color: "#fff", border: "none", borderRadius: 14, padding: "16px 32px", fontSize: 16, fontWeight: 700, cursor: "pointer", width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 },
  divider:     { border: "none", borderTop: "1px solid #f0f0f0", margin: "12px 0" },
};

// ─── Info Screen ──────────────────────────────────────────────────────────────
function InfoScreen({ onNext }) {
  const [expanded, setExpanded] = useState(false);

  const factors = [
    { title: "Risk Tolerance",    desc: "Low, Moderate, or High risk appetite",       color: "#f57c00", bg: "rgba(245,124,0,0.08)",   border: "rgba(245,124,0,0.25)",   emoji: "📈" },
    { title: "Investment Horizon",desc: "Short-term, medium, or long-term goals",     color: "#1976d2", bg: "rgba(25,118,210,0.08)",   border: "rgba(25,118,210,0.25)",  emoji: "⏱️" },
    { title: "Investment Goals",  desc: "Retirement, wealth, tax saving, etc.",       color: "#388e3c", bg: "rgba(56,142,60,0.08)",    border: "rgba(56,142,60,0.25)",   emoji: "🎯" },
    { title: "Investment Amount", desc: "Optimal diversification based on budget",    color: "#7b1fa2", bg: "rgba(123,31,162,0.08)",   border: "rgba(123,31,162,0.25)",  emoji: "₹" },
  ];

  const strategies = [
    { title: "1. Risk Assessment",       color: "#f57c00", desc: "We match your risk tolerance with appropriate fund categories:", points: ["Low Risk → 70% Debt + 30% Liquid Funds (Capital preservation)", "Moderate Risk → 50% Hybrid + 30% Debt + 20% Equity (Balanced growth)", "High Risk → 60% Equity + 25% Mid Cap + 15% Debt (Maximum returns)"] },
    { title: "2. Time Horizon Analysis", color: "#1976d2", desc: "Investment duration determines fund selection:", points: ["Short-term (<3 years) → Liquid & Short Duration funds for stability", "Medium-term (3–5 years) → Balanced allocation for steady growth", "Long-term (>5 years) → Higher equity exposure for wealth creation"] },
    { title: "3. Goal-Based Selection",  color: "#388e3c", desc: "Your investment goals shape fund choices:", points: ["Retirement → Long-term equity funds for compounding", "Tax Saving → ELSS funds with Section 80C benefits", "Wealth Creation → Growth-oriented equity funds", "Education/Short-term → Debt & liquid funds for safety"] },
    { title: "4. Dynamic Allocation",    color: "#7b1fa2", desc: "Number of funds varies based on investment amount (always totals 100%):", points: ["< ₹5,000 → 1 fund (focused approach)", "₹5,000–₹10,000 → 2 funds (basic diversification)", "₹10,000–₹25,000 → 3 funds (balanced portfolio)", "₹25,000–₹50,000 → 4 funds (enhanced diversification)", "> ₹50,000 → 5+ funds (maximum diversification)"] },
  ];

  return (
    <div style={S.page}>
      {/* Hero */}
      <div style={{ background: "linear-gradient(135deg,#1565c0 0%,#1976d2 60%,#7b1fa2 100%)", padding: "52px 24px 44px", textAlign: "center", color: "#fff" }}>
        <div style={{ fontSize: 58 }}>💼</div>
        <div style={{ fontSize: 36, fontWeight: 800, marginTop: 14 }}>MF Advisor</div>
        <div style={{ fontSize: 17, color: "rgba(255,255,255,0.85)", marginTop: 8 }}>Smart Mutual Fund Recommendations</div>
        <button onClick={onNext} style={{ marginTop: 28, background: "#fff", color: "#1565c0", border: "none", borderRadius: 14, padding: "14px 40px", fontSize: 16, fontWeight: 700, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 8 }}>
          🚀 Get Started →
        </button>
      </div>

      <div style={{ maxWidth: 760, margin: "0 auto", padding: "32px 20px 48px" }}>
        <div style={{ fontSize: 24, fontWeight: 700, color: "#111", marginBottom: 4 }}>How It Works</div>
        <div style={{ fontSize: 15, color: "#888", marginBottom: 24 }}>We analyze 4 key factors:</div>

        {factors.map((f) => (
          <div key={f.title} style={{ display: "flex", alignItems: "center", gap: 16, padding: 16, borderRadius: 14, marginBottom: 12, background: f.bg, border: `1px solid ${f.border}` }}>
            <div style={{ width: 48, height: 48, borderRadius: 12, background: f.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, flexShrink: 0 }}>{f.emoji}</div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: f.color }}>{f.title}</div>
              <div style={{ fontSize: 13, color: "#666", marginTop: 3 }}>{f.desc}</div>
            </div>
          </div>
        ))}

        {/* Expandable strategy */}
        <div style={{ borderRadius: 14, overflow: "hidden", marginBottom: 20, border: "1px solid #ddd" }}>
          <div onClick={() => setExpanded(!expanded)} style={{ background: "linear-gradient(90deg,#1565c0,#7b1fa2)", padding: "14px 20px", display: "flex", alignItems: "center", gap: 14, cursor: "pointer" }}>
            <span style={{ fontSize: 26 }}>🧠</span>
            <div style={{ flex: 1 }}>
              <div style={{ color: "#fff", fontSize: 15, fontWeight: 700 }}>Our Selection Strategy</div>
              <div style={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }}>Click to learn how we choose funds</div>
            </div>
            <span style={{ color: "#fff", fontSize: 16, transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>▼</span>
          </div>
          {expanded && (
            <div style={{ background: "#fff", padding: 24 }}>
              {strategies.map((s2) => (
                <div key={s2.title} style={{ marginBottom: 20 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                    <div style={{ padding: "5px 8px", borderRadius: 8, background: s2.color + "22" }}><span style={{ color: s2.color }}>✓</span></div>
                    <span style={{ fontSize: 15, fontWeight: 700, color: s2.color }}>{s2.title}</span>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "#333", marginBottom: 8 }}>{s2.desc}</div>
                  {s2.points.map((p, i) => (
                    <div key={i} style={{ display: "flex", gap: 8, marginBottom: 5, paddingLeft: 4 }}>
                      <div style={{ width: 6, height: 6, borderRadius: "50%", background: s2.color, flexShrink: 0, marginTop: 6 }} />
                      <span style={{ fontSize: 13, color: "#555" }}>{p}</span>
                    </div>
                  ))}
                </div>
              ))}
              <div style={{ background: "#fffde7", border: "1px solid #ffe082", borderRadius: 10, padding: 14, display: "flex", gap: 12, marginTop: 8 }}>
                <span style={{ fontSize: 18 }}>✨</span>
                <span style={{ fontSize: 13, fontWeight: 500 }}>All recommendations use real-time NAV data and historical performance metrics to ensure accuracy.</span>
              </div>
            </div>
          )}
        </div>

        {/* Real-time data */}
        <div style={{ background: "linear-gradient(90deg,#e3f0fb,#dce8f7)", borderRadius: 14, padding: "18px 24px", display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 36 }}>🛡️</span>
          <div>
            <div style={{ fontSize: 17, fontWeight: 700 }}>Real-time Data</div>
            <div style={{ fontSize: 13, color: "#555", marginTop: 2 }}>Live NAV & verified historical returns from MFApi</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Input Screen ─────────────────────────────────────────────────────────────
function InputScreen({ onBack, onResults }) {
  const [budget, setBudget]   = useState("");
  const [age, setAge]         = useState("");
  const [horizon, setHorizon] = useState("");
  const [risk, setRisk]       = useState("low");
  const [goals, setGoals]     = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  const toggleGoal = (v) => setGoals((p) => p.includes(v) ? p.filter((g) => g !== v) : [...p, v]);

  const handleSubmit = async () => {
    if (!budget || !age || !horizon) { setError("Please fill all fields."); return; }
    if (goals.length === 0)          { setError("Please select at least one goal."); return; }
    setError(""); setLoading(true);
    try {
      const data = await getRecommendations({ budget: parseFloat(budget), age: parseInt(age), risk_tolerance: risk, investment_horizon: parseInt(horizon), goals });
      onResults(data, parseFloat(budget));
    } catch (e) {
      setError("Error: " + e.message + " — Make sure the backend is running: uvicorn main:app --reload --port 8000");
    } finally { setLoading(false); }
  };

  return (
    <div style={S.page}>
      {/* AppBar */}
      <div style={S.appBar}>
        <button onClick={onBack} style={S.backBtn}>←</button>
        <span style={{ fontSize: 17, fontWeight: 700, color: "#fff" }}>Your Investment Profile</span>
      </div>

      {/* Hero */}
      <div style={S.hero}>
        <div style={{ fontSize: 48 }}>👤</div>
        <div style={{ fontSize: 20, fontWeight: 700, marginTop: 10 }}>Tell us about yourself</div>
        <div style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", marginTop: 5 }}>We'll find the perfect funds for you</div>
      </div>

      <div style={S.body}>
        {/* Basic Details */}
        <div style={S.card}>
          <div style={S.sectionHead}>Basic Details</div>
          {[
            { label: "Investment Budget (₹)", icon: "₹", val: budget, set: setBudget, ph: "e.g. 100000" },
            { label: "Your Age",              icon: "🎂", val: age,    set: setAge,    ph: "e.g. 22"     },
            { label: "Investment Horizon (years)", icon: "📅", val: horizon, set: setHorizon, ph: "e.g. 25" },
          ].map((f) => (
            <div key={f.label} style={S.inputWrap}>
              <label style={S.label}>{f.label}</label>
              <div style={{ position: "relative" }}>
                <span style={S.iconLeft}>{f.icon}</span>
                <input type="number" value={f.val} onChange={(e) => f.set(e.target.value)} placeholder={f.ph} style={S.input} />
              </div>
            </div>
          ))}
        </div>

        {/* Risk Tolerance */}
        <div style={S.card}>
          <div style={S.sectionHead}>Risk Tolerance</div>
          {RISK_OPTIONS.map((r) => {
            const sel = risk === r.value;
            return (
              <div key={r.value} onClick={() => setRisk(r.value)}
                style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 16px", borderRadius: 12, border: `${sel ? 2 : 1}px solid ${sel ? r.color : "#e0e0e0"}`, background: sel ? r.bg : "#fafafa", cursor: "pointer", marginBottom: 10, transition: "all 0.15s" }}>
                <span style={{ fontSize: 20, color: sel ? r.color : "#aaa", width: 28, textAlign: "center" }}>{r.icon}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 15, color: sel ? r.color : "#222" }}>{r.label}</div>
                  <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>{r.desc}</div>
                </div>
                <span style={{ fontSize: 20 }}>{sel ? "✅" : "⭕"}</span>
              </div>
            );
          })}
        </div>

        {/* Investment Goals */}
        <div style={S.card}>
          <div style={S.sectionHead}>Investment Goals</div>
          {GOALS.map((g, i) => {
            const checked = goals.includes(g.value);
            return (
              <div key={g.value} onClick={() => toggleGoal(g.value)}
                style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "13px 0", borderBottom: i < GOALS.length - 1 ? "1px solid #f4f4f4" : "none", cursor: "pointer" }}>
                <span style={{ fontSize: 15, color: "#222" }}>{g.label}</span>
                <div style={{ width: 22, height: 22, borderRadius: 5, border: `2px solid ${checked ? "#1976d2" : "#bbb"}`, background: checked ? "#1976d2" : "#fff", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "all 0.15s" }}>
                  {checked && <span style={{ color: "#fff", fontSize: 13, fontWeight: 700, lineHeight: 1 }}>✓</span>}
                </div>
              </div>
            );
          })}
        </div>

        {/* Submit */}
        <button onClick={handleSubmit} disabled={loading} style={{ ...S.btnBlue, opacity: loading ? 0.7 : 1 }}>
          {loading ? "Fetching recommendations…" : "✨ Get Recommendations"}
        </button>
        {error && <div style={{ color: "#c62828", fontSize: 13, marginTop: 12, lineHeight: 1.5 }}>{error}</div>}
      </div>
    </div>
  );
}

// ─── Fund Card ────────────────────────────────────────────────────────────────
function FundCard({ fund }) {
  const risk     = fund.risk_level || "";
  const color    = getCategoryColor(risk);
  const nav      = fund.nav != null ? "₹" + parseFloat(fund.nav).toFixed(2) : "—";
  const alloc    = fund.allocation_percentage != null ? Math.round(fund.allocation_percentage) + "%" : "—";
  const investAmt= fund.allocation_amount != null ? "₹" + Math.round(fund.allocation_amount).toLocaleString("en-IN") : "—";
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
          style={{ ...S.btnBlue, marginTop: 14, borderRadius: 10, padding: "12px", fontSize: 14, width: "100%" }}>
          🔗 Invest Now
        </button>
      </div>
    </div>
  );
}

// ─── Results Screen ───────────────────────────────────────────────────────────
function ResultsScreen({ onBack, results, budget }) {
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
        <div style={{ fontSize: 15, color: "rgba(255,255,255,0.85)", marginTop: 6 }}>{recs.length} Fund{recs.length !== 1 ? "s" : ""} Recommended</div>
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

// ─── App root ─────────────────────────────────────────────────────────────────
export default function App() {
  const [screen, setScreen] = useState("info");
  const [results, setResults] = useState(null);
  const [budget, setBudget] = useState(0);

  const handleResults = (data, b) => { setResults(data); setBudget(b); setScreen("results"); };

  return (
    <>
      {screen === "info"    && <InfoScreen    onNext={() => setScreen("input")} />}
      {screen === "input"   && <InputScreen   onBack={() => setScreen("info")} onResults={handleResults} />}
      {screen === "results" && <ResultsScreen onBack={() => setScreen("input")} results={results} budget={budget} />}
    </>
  );
}