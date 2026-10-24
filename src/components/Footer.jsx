import { Link } from "react-router-dom";
import { COMPLIANCE, SEBI_LINKS } from "../constants/compliance";
import "../styles/Footer.css";

export default function Footer() {
  const c = COMPLIANCE;
  return (
    <footer className="footer">
      <div className="footer__inner">
        <div className="footer__brand">{c.legalEntity}</div>
        <div className="footer__line">
          {c.registrationType} · Reg. No. {c.registrationNumber} · Validity: {c.registrationValidity} ·
          BASL Membership ID: {c.baslMembershipId} · CIN: {c.cin}
        </div>
        <div className="footer__line">{c.address}</div>
        <div className="footer__line">
          Principal Officer: {c.principalOfficer.name}, {c.principalOfficer.email}, {c.principalOfficer.phone}
        </div>
        <div className="footer__line">
          Compliance Officer: {c.complianceOfficer.name}, {c.complianceOfficer.email}, {c.complianceOfficer.phone}
        </div>
        <div className="footer__line">
          Grievances: <a href={`mailto:${c.grievanceEmail}`}>{c.grievanceEmail}</a>. If unresolved, lodge a complaint on{" "}
          <a href={SEBI_LINKS.scores} target="_blank" rel="noopener noreferrer">SEBI SCORES</a> or the{" "}
          <a href={SEBI_LINKS.odr} target="_blank" rel="noopener noreferrer">Smart ODR portal</a>. {c.sebiOffice}.
        </div>
        <div className="footer__line footer__links">
          <Link to="/investor-charter">Investor Charter</Link>
          <Link to="/complaints">Complaints data</Link>
          <Link to="/how-advice-works">How our advice works</Link>
          <Link to="/privacy">Privacy Notice</Link>
        </div>
        <div className="footer__line footer__muted">
          Investments in securities market are subject to market risks. Read all the related documents carefully before investing.
        </div>
      </div>
    </footer>
  );
}
