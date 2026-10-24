import { useNavigate } from "react-router-dom";
import { COMPLIANCE, SEBI_LINKS } from "../constants/compliance";
import { CHARTER, CHARTER_SOURCE, IA_LIST_URL } from "../constants/investorCharter";
import "../styles/InfoPage.css";
import "../styles/shared.css";
import AppBar from "./AppBar";

function Items({ items, ordered }) {
  const List = ordered ? "ol" : "ul";
  return (
    <List className={ordered ? "charterList charterList--ordered" : "charterList"}>
      {items.map((item) => typeof item === "string"
        ? <li key={item}>{item}</li>
        : (
          <li key={item.text}>
            <b>{item.text}</b>
            <Items items={item.sub} ordered={item.ordered} />
          </li>
        ))}
    </List>
  );
}

export default function InvestorCharterScreen() {
  const navigate = useNavigate();
  return (
    <div className="page">
      <AppBar title="Investor Charter" onBack={() => navigate(-1)} />
      <div className="body infoPage">
        <h1>Investor Charter for Investment Advisers</h1>
        <p className="mutedText">
          As prescribed by SEBI in circular {CHARTER_SOURCE.circular} dated {CHARTER_SOURCE.date}.{" "}
          <a href={CHARTER_SOURCE.url} target="_blank" rel="noopener noreferrer">Read the circular</a>.
        </p>

        {CHARTER.map((section) => (
          <section key={section.title} className="card">
            <h2>{section.title}</h2>
            <Items items={section.items} />
          </section>
        ))}

        <section className="card">
          <h2>Useful links</h2>
          <ul className="charterList">
            <li><a href={IA_LIST_URL} target="_blank" rel="noopener noreferrer">List of SEBI registered Investment Advisers</a></li>
            <li><a href={SEBI_LINKS.scores} target="_blank" rel="noopener noreferrer">SEBI SCORES 2.0</a></li>
            <li><a href={SEBI_LINKS.odr} target="_blank" rel="noopener noreferrer">Smart ODR portal</a></li>
            <li>Our grievance email: <a href={`mailto:${COMPLIANCE.grievanceEmail}`}>{COMPLIANCE.grievanceEmail}</a></li>
          </ul>
        </section>
      </div>
    </div>
  );
}
