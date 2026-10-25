import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getHealth } from "../api";
import { useAuth } from "../auth";
import { FACTORS, STRATEGIES } from "../constants/strategies";
import "../styles/InfoScreen.css";
import AppBar from "./AppBar";
import Disclaimer from "./Disclaimer";

// Illustration only: the hero card shows what a review looks like, not anyone's real portfolio.
const SAMPLE_FUNDS = [
  { name: "Flexi Cap Fund", cat: "Flexi Cap", status: "in_form", label: "Top 25%", value: "4,82,150", ret: "+18.4%" },
  { name: "Large Cap Index Fund", cat: "Large Cap", status: "on_track", label: "Above average", value: "3,10,400", ret: "+13.1%" },
  { name: "Small Cap Fund", cat: "Small Cap", status: "out_of_form", label: "Bottom 25%", value: "1,95,700", ret: "+6.2%" },
];

const STEPS = [
  { n: "01", title: "Tell us about you", text: "Six short steps: your goal, timeline, finances and how you feel about risk." },
  { n: "02", title: "Get a ranked plan", text: "An asset mix and specific Direct-Growth funds, each with the evidence behind it." },
  { n: "03", title: "Keep it on track", text: "Bring in your current funds and see which to keep, watch or replace." },
];

function HeroPreview() {
  return (
    <div className="preview" aria-hidden="true">
      <div className="preview__glow" />
      <div className="preview__card">
        <div className="preview__head">
          <div>
            <div className="preview__label">Portfolio value</div>
            <div className="preview__value num">₹9,88,250</div>
          </div>
          <div className="preview__badge">Sample</div>
        </div>
        <div className="preview__stats">
          <div><span>Invested</span><b className="num">₹7,40,000</b></div>
          <div><span>Returns (XIRR)</span><b className="num preview__pos">14.6%</b></div>
          <div><span>Funds</span><b className="num">3</b></div>
        </div>
        <svg className="preview__chart" viewBox="0 0 300 80" preserveAspectRatio="none">
          <defs>
            <linearGradient id="pvFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--accent)" stopOpacity="0.35" />
              <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d="M0 64 C30 60 45 66 70 54 S110 40 130 46 S170 30 195 28 S240 20 260 14 S290 10 300 6 L300 80 L0 80 Z" fill="url(#pvFill)" />
          <path d="M0 64 C30 60 45 66 70 54 S110 40 130 46 S170 30 195 28 S240 20 260 14 S290 10 300 6" fill="none"
            stroke="var(--accent)" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
        </svg>
        {SAMPLE_FUNDS.map((f) => (
          <div key={f.name} className="preview__row">
            <div className="preview__fund">
              <div className="preview__name">{f.name}</div>
              <div className="preview__cat">{f.cat}</div>
            </div>
            <div className="preview__right">
              <span className={`statusChip statusChip--${f.status}`}>{f.label}</span>
              <span className="preview__ret num">{f.ret}</span>
            </div>
          </div>
        ))}
        <div className="preview__tip">
          <span>💡</span> Your small cap fund is in the bottom quarter of its category. See better-ranked alternatives.
        </div>
      </div>
    </div>
  );
}

export default function InfoScreen() {
  const { panEnabled } = useAuth();
  const [expanded, setExpanded] = useState(false);
  const [ranked, setRanked] = useState(null);

  useEffect(() => {
    getHealth().then((h) => setRanked(h.funds_ranked)).catch(() => {});
  }, []);

  return (
    <div className="page">
      <AppBar />

      <section className="landingHero">
        <div className="landingHero__inner">
          <div className="landingHero__copy">
            <div className="pill"><span className="pill__dot" /> Re-ranked every night from AMFI data</div>
            <h1 className="landingHero__title">
              Mutual funds, <span className="gradText">ranked honestly.</span><br />Planned around your goals.
            </h1>
            <p className="landingHero__sub">
              Get a goal-based SIP plan with specific Direct funds, or find out how the funds you already own really
              stack up against their category. Clear reasons, no jargon.
            </p>
            <div className="landingHero__actions">
              <Link className="btnWhite" to="/plan">Build my plan <span aria-hidden="true">→</span></Link>
              <Link className="btnGhost" to="/review">Review my portfolio</Link>
            </div>
            <ul className="checkRow">
              <li>Direct plans only</li>
              <li>No login needed to start</li>
              <li>{panEnabled ? "Import with your PAN" : "Import your CAS statement"}</li>
            </ul>
          </div>
          <HeroPreview />
        </div>
      </section>

      <section className="statBand">
        <div className="statBand__inner">
          <div className="stat"><b className="num">{ranked ? `${ranked.toLocaleString("en-IN")}+` : "500+"}</b><span>funds ranked</span></div>
          <div className="stat"><b className="num">17</b><span>fund categories</span></div>
          <div className="stat"><b>Nightly</b><span>fresh NAV data</span></div>
          <div className="stat"><b>4 tiers</b><span>Top 25% to bottom 25%</span></div>
        </div>
      </section>

      <div className="landing">
        <section className="landingSection">
          <div className="eyebrow">What you can do</div>
          <h2 className="landingSection__title">Two tools, one honest view of your money</h2>
          <div className="featureGrid">
            <Link to="/plan" className="feature">
              <div className="feature__icon">🎯</div>
              <div className="feature__title">Plan a goal</div>
              <p className="feature__text">Retirement, a home, your child's education or just wealth. We work out the SIP,
                the asset mix and the funds.</p>
              <ul className="feature__list">
                <li>Risk scored on ability <i>and</i> willingness</li>
                <li>Pessimistic, expected and optimistic projections</li>
                <li>Uses the funds you already hold</li>
              </ul>
              <span className="feature__cta">Start planning →</span>
            </Link>
            <Link to="/review" className="feature">
              <div className="feature__icon">📊</div>
              <div className="feature__title">Review your portfolio</div>
              <p className="feature__text">Every fund rated against its category, with what you've really earned and where
                you're overpaying.</p>
              <ul className="feature__list">
                <li>XIRR, tax lots and Regular-plan costs</li>
                <li>Duplicate funds and stock overlap</li>
                <li>Keep, watch or switch, fund by fund</li>
              </ul>
              <span className="feature__cta">Review my funds →</span>
            </Link>
          </div>
        </section>

        <section className="landingSection">
          <div className="eyebrow">How it works</div>
          <h2 className="landingSection__title">From questions to a plan in about five minutes</h2>
          <div className="stepsGrid">
            {STEPS.map((s) => (
              <div key={s.n} className="stepCard">
                <div className="stepCard__n">{s.n}</div>
                <div className="stepCard__title">{s.title}</div>
                <p className="stepCard__text">{s.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="landingSection">
          <div className="eyebrow">What shapes your plan</div>
          <h2 className="landingSection__title">Four things about you, and data on every fund in India</h2>
          <div className="factorGrid">
            {FACTORS.map((f) => (
              <div key={f.title} className="factorCard">
                <div className="factorIcon">{f.emoji}</div>
                <div>
                  <div className="factorTitle">{f.title}</div>
                  <div className="factorDesc">{f.desc}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="expansionBox">
            <button type="button" className="expansionHeader" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
              <span className="expansionHeader__icon">🧠</span>
              <div style={{ flex: 1 }}>
                <div className="expansionHeader__title">Our selection method</div>
                <div className="expansionHeader__subtitle">How we build your plan and choose funds</div>
              </div>
              <span className={`expansionChevron ${expanded ? "expansionChevron--open" : ""}`}>▾</span>
            </button>
            {expanded && (
              <div className="expansionBody">
                {STRATEGIES.map((s) => (
                  <div key={s.title} className="strategySection">
                    <div className="strategyTitle">{s.title}</div>
                    <div className="strategyDesc">{s.desc}</div>
                    <ul className="strategyPoints">
                      {s.points.map((p, i) => <li key={i}>{p}</li>)}
                    </ul>
                  </div>
                ))}
                <div className="amberNotice">
                  <span>✨</span>
                  <span className="amberNotice__text">
                    Rankings are rebuilt every night from AMFI's official NAV data. No AI is used:{" "}
                    <Link to="/how-advice-works">how our advice works</Link>.
                  </span>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="ctaBand">
          <div>
            <div className="ctaBand__title">Ready to see where you stand?</div>
            <div className="ctaBand__text">Start a plan or check your funds. You don't need an account for either.</div>
          </div>
          <div className="ctaBand__actions">
            <Link className="btnWhite" to="/plan">Build my plan</Link>
            <Link className="btnGhost" to="/review">Review my portfolio</Link>
          </div>
        </section>

        <Disclaimer />
      </div>
    </div>
  );
}
