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
              <b>Fund selection:</b> every night, the open-ended Direct-Growth funds in the 17 SEBI categories we use
              are ranked against others in their category. A fund needs at least 3 years of history to be ranked (1 to 2
              years for liquid, money market and other debt funds), so newly launched funds are not recommended. Funds
              in other categories, such as sector, theme and international funds, are not recommended either. Because
              past returns alone predict future returns poorly, they make up only about half of a fund&apos;s score:
              <ul className="charterList">
                <li><b>Track record (about 50%):</b> 3- and 5-year returns, consistency (rolling returns), return for
                  the risk taken, volatility and worst fall.</li>
                <li><b>Against its index (about 20-25%, equity funds):</b> how much it earned above an index fund
                  tracking its category&apos;s index (for example Nifty Smallcap 250 for small cap funds), how often it
                  beat that index over 3-year periods, and how much of the market&apos;s falls it took.</li>
                <li><b>Expense ratio (10%):</b> the yearly cost of the Direct plan, compared with its category. It is
                  the one drag on returns known in advance.</li>
                <li><b>Fund size (12%):</b> very large funds in small, mid and flexi cap categories score lower,
                  because money spread across hundreds of stocks means one company doing well moves the NAV little,
                  and big funds struggle to buy or sell smaller stocks. Funds under ₹500 crore (₹1,000 crore for debt)
                  also score lower, as they are more exposed to closure and to a few large investors leaving.</li>
                <li><b>Credit quality (5-7%, debt funds):</b> the share of the portfolio rated below AAA, A1+ or
                  sovereign.</li>
              </ul>
              The weights shift with your risk profile; a cautious profile puts more weight on falls. When choosing,
              the plan spreads funds across fund houses and passes over funds whose fund manager changed in the last
              year, since the track record belongs to the people who built it.
            </li>
            <li>
              <b>Portfolio review:</b> each fund you hold is rated by where it ranks in its category (top quarter "in form"
              to bottom quarter "out of form"). The portfolio is checked for costs, Regular plans, funds that own
              largely the same stocks (from their monthly portfolio disclosures), funds too large for their category,
              fund manager changes and drift from your plan.
            </li>
            <li>
              <b>Data sources:</b> NAVs from AMFI and mfapi.in; expense ratios, fund managers and monthly portfolios
              from Kuvera&apos;s public fund data, which compiles the fund houses&apos; disclosures; fund size from AMFI.
              Fund facts are refreshed weekly.
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
            <li>Rankings lean on past performance and published fund data. Past performance does not guarantee future
              returns, and no measure here can.</li>
            <li>Fund manager changes are tracked from October 2026, when we started recording them; earlier changes
              are not known to us.</li>
            <li>Portfolio data is the fund houses&apos; month-end disclosure, so it can be up to about six weeks old.</li>
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
