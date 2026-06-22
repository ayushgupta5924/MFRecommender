import { useState } from "react";
import { getRecommendations } from "../api";
import { GOALS } from "../constants/goals";
import { RISK_OPTIONS } from "../constants/risk";
import { S } from "../styles/shared";

export default function InputScreen({ onBack, onResults }) {
  const [budget, setBudget]   = useState("");
  const [age, setAge]         = useState("");
  const [horizon, setHorizon] = useState("");
  const [risk, setRisk]       = useState("low");
  const [goals, setGoals]     = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  const toggleGoal = (v) =>
    setGoals((prev) => prev.includes(v) ? prev.filter((g) => g !== v) : [...prev, v]);

  const handleSubmit = async () => {
    if (!budget || !age || !horizon) { setError("Please fill all fields."); return; }
    if (goals.length === 0) { setError("Please select at least one goal."); return; }
    setError("");
    setLoading(true);
    try {
      const data = await getRecommendations({
        budget: parseFloat(budget),
        age: parseInt(age),
        risk_tolerance: risk,
        investment_horizon: parseInt(horizon),
        goals,
      });
      onResults(data, parseFloat(budget));
    } catch (e) {
      setError("Error: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const Field = ({ label, icon, value, onChange, placeholder }) => (
    <div style={S.inputWrap}>
      <label style={S.label}>{label}</label>
      <div style={{ position: "relative" }}>
        <span style={S.iconLeft}>{icon}</span>
        <input type="number" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={S.input} />
      </div>
    </div>
  );

  return (
    <div style={S.page}>
      <div style={S.appBar}>
        <button onClick={onBack} style={S.backBtn}>←</button>
        <span style={{ fontSize: 17, fontWeight: 700, color: "#fff" }}>Your Investment Profile</span>
      </div>

      <div style={S.hero}>
        <div style={{ fontSize: 48 }}>👤</div>
        <div style={{ fontSize: 20, fontWeight: 700, marginTop: 10 }}>Tell us about yourself</div>
        <div style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", marginTop: 5 }}>We'll find the perfect funds for you</div>
      </div>

      <div style={S.body}>
        {/* Basic Details */}
        <div style={S.card}>
          <div style={S.sectionHead}>Basic Details</div>
          <Field label="Investment Budget (₹)" icon="₹" value={budget} onChange={setBudget} placeholder="e.g. 100000" />
          <Field label="Your Age" icon="🎂" value={age} onChange={setAge} placeholder="e.g. 22" />
          <Field label="Investment Horizon (years)" icon="📅" value={horizon} onChange={setHorizon} placeholder="e.g. 5" />
        </div>

        {/* Risk Tolerance */}
        <div style={S.card}>
          <div style={S.sectionHead}>Risk Tolerance</div>
          {RISK_OPTIONS.map((r) => {
            const sel = risk === r.value;
            return (
              <div key={r.value} onClick={() => setRisk(r.value)}
                style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 16px", borderRadius: 12, border: `${sel ? 2 : 1}px solid ${sel ? r.color : "#e0e0e0"}`, background: sel ? r.bg : "#fafafa", cursor: "pointer", marginBottom: 10, transition: "all 0.15s" }}>
                <div style={{ width: 44, height: 44, borderRadius: 11, background: sel ? r.color : "#eee", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, flexShrink: 0 }}>{r.icon}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 15, color: sel ? r.color : "#222" }}>{r.label}</div>
                  <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>{r.desc}</div>
                </div>
                <span style={{ fontSize: 22, color: sel ? r.color : "#ccc" }}>{sel ? "✅" : "⭕"}</span>
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

        <button onClick={handleSubmit} disabled={loading} style={{ ...S.btnBlue, opacity: loading ? 0.7 : 1 }}>
          {loading ? "Fetching recommendations…" : "✨ Get Recommendations"}
        </button>
        {error && <div style={{ color: "#c62828", fontSize: 13, marginTop: 12, lineHeight: 1.5 }}>{error}</div>}
      </div>
    </div>
  );
}