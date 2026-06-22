import { useState } from "react";
import { FACTORS, STRATEGIES } from "../constants/strategies";

export default function InfoScreen({ onNext }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div style={{ minHeight: "100vh", background: "#f0f2f5" }}>
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

        {FACTORS.map((f) => (
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
              {STRATEGIES.map((s) => (
                <div key={s.title} style={{ marginBottom: 20 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                    <div style={{ padding: "5px 8px", borderRadius: 8, background: s.color + "22" }}><span style={{ color: s.color }}>✓</span></div>
                    <span style={{ fontSize: 15, fontWeight: 700, color: s.color }}>{s.title}</span>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "#333", marginBottom: 8 }}>{s.desc}</div>
                  {s.points.map((p, i) => (
                    <div key={i} style={{ display: "flex", gap: 8, marginBottom: 5, paddingLeft: 4 }}>
                      <div style={{ width: 6, height: 6, borderRadius: "50%", background: s.color, flexShrink: 0, marginTop: 6 }} />
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