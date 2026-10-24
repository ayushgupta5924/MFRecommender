import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../auth";

function initials(name) {
  const parts = (name || "").trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

export default function AppBar({ title, onBack, extra }) {
  const { user, accountsEnabled } = useAuth();
  return (
    <div className="appBar">
      {onBack
        ? <button className="backBtn" aria-label="Back" onClick={onBack}>←</button>
        : <Link to="/" className="appBar__brand" aria-label="Home">💼</Link>}
      <span className="appBar__title">{title}</span>
      {extra}
      <nav className="appBar__nav">
        <NavLink to="/review" className="appBar__link">Review</NavLink>
        {user && (
          <NavLink to="/account" className="appBar__avatar" title={user.full_name} aria-label="Your account">
            {initials(user.full_name)}
          </NavLink>
        )}
        {accountsEnabled && user === null && <NavLink to="/login" className="appBar__link appBar__link--solid">Log in</NavLink>}
      </nav>
    </div>
  );
}
