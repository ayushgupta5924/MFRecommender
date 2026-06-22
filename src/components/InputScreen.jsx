import { useState } from "react";
import { getRecommendations } from "../api";
import { GOALS } from "../constants/goals";
import { RISK_OPTIONS } from "../constants/risk";
import "../styles/InputScreen.css";
import "../styles/shared.css";

function Field({ label, icon, value, onChange, placeholder }) {
  return (
    <div className="fieldWrap">
      <label className="fieldLabel">{label}</label>
      <div style={{ position: "relative" }}>
        <span className="fieldIcon">{icon}</span>
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="fieldInput"
        />
      </div>
    </div>
  );
}

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

  return (
    <div className="page">
      <div className="appBar">
        <button className="backBtn" onClick={onBack}>←</button>
        <span className="appBar__title">Your Investment Profile</span>
      </div>

      <div className="hero">
        <div className="hero__icon">👤</div>
        <div className="hero__title">Tell us about yourself</div>
        <div className="hero__subtitle">We'll find the perfect funds for you</div>
      </div>

      <div className="body">
        {/* Basic Details */}
        <div className="card">
          <div className="card__title">Basic Details</div>
          <Field label="Investment Budget (₹)" icon="₹" value={budget} onChange={setBudget} placeholder="e.g. 100000" />
          <Field label="Your Age" icon="🎂" value={age} onChange={setAge} placeholder="e.g. 22" />
          <Field label="Investment Horizon (years)" icon="📅" value={horizon} onChange={setHorizon} placeholder="e.g. 5" />
        </div>

        {/* Risk Tolerance */}
        <div className="card">
          <div className="card__title">Risk Tolerance</div>
          {RISK_OPTIONS.map((r) => {
            const sel = risk === r.value;
            return (
              <div key={r.value} onClick={() => setRisk(r.value)}
                className={`riskOption ${sel ? "riskOption--selected" : ""}`}
                style={sel ? { borderColor: r.color, background: r.bg } : {}}>
                <div className="riskIcon" style={sel ? { background: r.color } : {}}>{r.icon}</div>
                <div style={{ flex: 1 }}>
                  <div className="riskLabel" style={sel ? { color: r.color } : {}}>{r.label}</div>
                  <div className="riskDesc">{r.desc}</div>
                </div>
                <span className="riskCheck" style={sel ? { color: r.color } : {}}>{sel ? "✅" : "⭕"}</span>
              </div>
            );
          })}
        </div>

        {/* Investment Goals */}
        <div className="card">
          <div className="card__title">Investment Goals</div>
          {GOALS.map((g) => {
            const checked = goals.includes(g.value);
            return (
              <div key={g.value} className="goalRow" onClick={() => toggleGoal(g.value)}>
                <span className="goalLabel">{g.label}</span>
                <div className={`goalCheckbox ${checked ? "goalCheckbox--checked" : ""}`}>
                  {checked && <span className="goalCheckmark">✓</span>}
                </div>
              </div>
            );
          })}
        </div>

        <button className="btnBlue" onClick={handleSubmit} disabled={loading}>
          {loading ? "Fetching recommendations…" : "✨ Get Recommendations"}
        </button>
        {error && <div className="errorText">{error}</div>}
      </div>
    </div>
  );
}