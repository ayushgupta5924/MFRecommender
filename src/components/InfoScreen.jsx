import { useState } from "react";
import { FACTORS, STRATEGIES } from "../constants/strategies";
import "../styles/InfoScreen.css";
import "../styles/shared.css";
import Disclaimer from "./Disclaimer";

export default function InfoScreen({ onNext }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="page">
      <div className="infoHero">
        <div className="infoHero__icon">💼</div>
        <div className="infoHero__title">MF Advisor</div>
        <div className="infoHero__subtitle">A mutual fund plan built from your goals, risk profile and real fund data</div>
        <button className="btnWhite" onClick={onNext}>🚀 Get Started →</button>
      </div>

      <div className="body">
        <Disclaimer />

        <div className="sectionTitle">How It Works</div>
        <div className="sectionSubtitle">We combine 4 factors about you with performance data for every fund in India:</div>

        <div className="factorGrid">
          {FACTORS.map((f) => (
            <div key={f.title} className="factorCard" style={{ background: f.bg, borderColor: f.border }}>
              <div className="factorIcon" style={{ background: f.color }}>{f.emoji}</div>
              <div>
                <div className="factorTitle" style={{ color: f.color }}>{f.title}</div>
                <div className="factorDesc">{f.desc}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="expansionBox">
          <button type="button" className="expansionHeader" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
            <span className="expansionHeader__icon">🧠</span>
            <div style={{ flex: 1 }}>
              <div className="expansionHeader__title">Our Selection Strategy</div>
              <div className="expansionHeader__subtitle">How we build your plan and choose funds</div>
            </div>
            <span className={`expansionChevron ${expanded ? "expansionChevron--open" : ""}`}>▼</span>
          </button>
          {expanded && (
            <div className="expansionBody">
              {STRATEGIES.map((s) => (
                <div key={s.title} className="strategySection">
                  <div className="strategyHeader">
                    <div className="strategyIconWrap" style={{ background: s.color + "22" }}>
                      <span style={{ color: s.color }}>✓</span>
                    </div>
                    <span className="strategyTitle" style={{ color: s.color }}>{s.title}</span>
                  </div>
                  <div className="strategyDesc">{s.desc}</div>
                  {s.points.map((p, i) => (
                    <div key={i} className="strategyPoint">
                      <div className="strategyDot" style={{ background: s.color }} />
                      <span className="strategyPointText">{p}</span>
                    </div>
                  ))}
                </div>
              ))}
              <div className="amberNotice">
                <span>✨</span>
                <span className="amberNotice__text">Rankings are rebuilt every night from AMFI's official NAV data.</span>
              </div>
            </div>
          )}
        </div>

        <div className="realtimeBox">
          <span className="realtimeBox__icon">🛡️</span>
          <div>
            <div className="realtimeBox__title">Updated Daily</div>
            <div className="realtimeBox__subtitle">Every Direct-Growth fund in India, re-ranked each night</div>
          </div>
        </div>
      </div>
    </div>
  );
}