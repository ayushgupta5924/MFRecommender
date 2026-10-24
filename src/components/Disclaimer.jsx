import { COMPLIANCE } from "../constants/compliance";
import "../styles/Disclaimer.css";

export default function Disclaimer() {
  return (
    <div className="disclaimer">
      <div className="disclaimer__badge">⚠️</div>
      <div className="disclaimer__content">
        <div className="disclaimer__title">Important Disclaimer</div>
        <p className="disclaimer__text">
          Mutual fund investments are subject to market risks; read all scheme-related documents carefully before
          investing. <strong>Past performance does not guarantee future returns</strong>, and projections are
          estimates, not promises. Suggestions are based only on the information you provide and on publicly
          available NAV data.
        </p>
        <p className="disclaimer__text">
          {COMPLIANCE.legalEntity} is a {COMPLIANCE.registrationType} (Reg. No. {COMPLIANCE.registrationNumber}).
          Registration granted by SEBI, membership of BASL and certification from NISM in no way guarantee
          performance of the intermediary or provide any assurance of returns to investors.
        </p>
      </div>
    </div>
  );
}
