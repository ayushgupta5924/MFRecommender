import { Link, useNavigate } from "react-router-dom";
import { COMPLIANCE } from "../constants/compliance";
import { STRATEGIES } from "../constants/strategies";
import "../styles/InfoPage.css";
import "../styles/shared.css";
import AppBar from "./AppBar";

// Disclosure of the extent and manner of automated / AI tools in our advice, as SEBI's Investment Advisers
// Regulations (regulation 18, as amended in December 2024) and the Investor Charter require.
export default function HowAdviceWorksScreen() {
  const navigate = useNavigate();
  return (
    <div className="page">
      <AppBar title="How our advice works" onBack={() => navigate(-1)} />
      <div className="body infoPage">
        <h1>How our advice is generated</h1>
        <p className="mutedText">Our disclosure on the use of automated tools and Artificial Intelligence.</p>

        <section className="card">
          <h2>Use of Artificial Intelligence</h2>
          <ul className="charterList">
            <li>
              <b>We do not use Artificial Intelligence</b>, machine learning or generative AI (such as chatbots or large
              language models) to produce advice, rank funds or assess your risk profile.
            </li>
            <li>
              Advice is produced by <b>rules-based software</b>: fixed, written rules that give the same answer every time
              for the same inputs. The rules are set, reviewed and approved by {COMPLIANCE.legalEntity}.
            </li>
            <li>
              {COMPLIANCE.legalEntity} remains solely responsible for all advice given through this website, including
              its accuracy and suitability, and for the security and confidentiality of your data.
            </li>
            <li>If we ever start using AI tools, we will update this page and tell existing clients before doing so.</li>
          </ul>
        </section>

        <section className="card">
          <h2>What the software does</h2>
          <ul className="charterList">
            <li>
              <b>Risk profile:</b> your answers give two scores, your ability to take risk (age, income, dependents,
              loans, savings) and your comfort with risk. We use the lower of the two. You see both before any advice.
            </li>
            <li>
              <b>Asset allocation:</b> your score, timeline, life stage and goal set the split between equity, hybrid and
              debt. Safety limits apply whatever your score, for example no equity for money needed within 3 years.
              Each plan explains which rules shaped it under "Why this mix".
            </li>
            <li>
              <b>Fund selection:</b> every night, every open-ended Direct-Growth fund published by AMFI is ranked against
              others in its SEBI category on 3- and 5-year returns, consistency (rolling returns), volatility and its
              worst fall, using NAV data from AMFI and mfapi.in. The plan picks well-ranked funds and spreads them across
              fund houses.
            </li>
            <li>
              <b>Portfolio review:</b> each fund you hold is rated by where it ranks in its category (top quarter "in form"
              to bottom quarter "out of form"), and the portfolio is checked for costs, duplication and drift from your
              plan.
            </li>
          </ul>
        </section>

        <section className="card">
          <h2>The rules in detail</h2>
          {STRATEGIES.map((s) => (
            <div key={s.title} style={{ marginBottom: 12 }}>
              <b>{s.title}</b>
              <div className="mutedText">{s.desc}</div>
              <ul className="charterList">{s.points.map((p) => <li key={p}>{p}</li>)}</ul>
            </div>
          ))}
        </section>

        <section className="card">
          <h2>Limits you should know</h2>
          <ul className="charterList">
            <li>Rankings use past NAV performance. Past performance does not guarantee future returns.</li>
            <li>Expense ratios, fund size, portfolio holdings and fund manager changes are not in our data and are not considered.</li>
            <li>Projections are estimates from category-level historical returns, shown as a range, not promises.</li>
            <li>The advice is only as good as the information you give. Please answer the questions accurately.</li>
          </ul>
        </section>

        <section className="card">
          <h2>Records and your data</h2>
          <p className="mutedText">
            As SEBI requires, we keep a record of your answers and the advice we gave for 5 years. See our{" "}
            <Link to="/privacy">Privacy Notice</Link> for what we store and your rights, and the{" "}
            <Link to="/investor-charter">Investor Charter</Link> for what you can expect from us.
          </p>
        </section>
      </div>
    </div>
  );
}
