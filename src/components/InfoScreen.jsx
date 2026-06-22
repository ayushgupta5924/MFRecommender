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
        <div className="infoHero__subtitle">Discover mutual funds based on your investor profile</div>
        <button className="btnWhite" onClick={onNext}>🚀 Get Started →</button>
      </div>

      <div className="body">
        <Disclaimer />

        <div className="sectionTitle">How It Works</div>
        <div className="sectionSubtitle">We analyze 4 key factors to match funds to your profile:</div>

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
          <div className="expansionHeader" onClick={() => setExpanded(!expanded)}>
            <span className="expansionHeader__icon">🧠</span>
            <div style={{ flex: 1 }}>
              <div className="expansionHeader__title">Our Selection Strategy</div>
              <div className="expansionHeader__subtitle">Click to learn how we choose funds</div>
            </div>
            <span className={`expansionChevron ${expanded ? "expansionChevron--open" : ""}`}>▼</span>
          </div>
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
                <span className="amberNotice__text">All fund data uses real-time NAV and historical performance metrics from MFApi.</span>
              </div>
            </div>
          )}
        </div>

        <div className="realtimeBox">
          <span className="realtimeBox__icon">🛡️</span>
          <div>
            <div className="realtimeBox__title">Real-time Data</div>
            <div className="realtimeBox__subtitle">Live NAV & verified historical returns from MFApi</div>
          </div>
        </div>
      </div>
    </div>
  );
}