import "../styles/Disclaimer.css";

export default function Disclaimer() {
  return (
    <div className="disclaimer">
      <span className="disclaimer__icon">⚠️</span>
      <p className="disclaimer__text">
        This tool is for <strong>educational and informational purposes only</strong>. 
        It does not constitute investment advice. Mutual fund investments are subject 
        to market risks. Please read all scheme-related documents carefully and consult 
        a SEBI-registered investment adviser before investing.
      </p>
    </div>
  );
}