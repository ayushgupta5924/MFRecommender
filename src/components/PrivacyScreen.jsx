import { useNavigate } from "react-router-dom";
import { COMPLIANCE } from "../constants/compliance";
import { PRIVACY, PRIVACY_VERSION } from "../constants/privacy";
import "../styles/InfoPage.css";
import "../styles/shared.css";
import { fmtDate } from "../utils/format";
import AppBar from "./AppBar";

export default function PrivacyScreen() {
  const navigate = useNavigate();
  const c = COMPLIANCE;
  return (
    <div className="page">
      <AppBar title="Privacy Notice" onBack={() => navigate(-1)} />
      <div className="body infoPage">
        <h1>Privacy Notice</h1>
        <p className="mutedText">
          How {c.legalEntity} handles your personal data. Last updated {fmtDate(PRIVACY_VERSION)}.
        </p>

        {PRIVACY.map((section) => (
          <section key={section.title} className="card">
            <h2>{section.title}</h2>
            {section.items ? (
              <div className="tableWrap">
                <table className="dataTable dataTable--text">
                  <thead><tr><th>Data</th><th>What exactly</th><th>Why we need it</th></tr></thead>
                  <tbody>
                    {section.items.map((i) => (
                      <tr key={i.what}><td><b>{i.what}</b></td><td>{i.detail}</td><td>{i.why}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <ul className="charterList">{section.points.map((p) => <li key={p}>{p}</li>)}</ul>
            )}
          </section>
        ))}

        <section className="card">
          <h2>Contact us</h2>
          <ul className="charterList">
            <li>{c.legalEntity}, {c.address}</li>
            <li>Grievances and privacy requests: <a href={`mailto:${c.grievanceEmail}`}>{c.grievanceEmail}</a></li>
            <li>Compliance Officer: {c.complianceOfficer.name}, <a href={`mailto:${c.complianceOfficer.email}`}>{c.complianceOfficer.email}</a></li>
          </ul>
        </section>
      </div>
    </div>
  );
}
