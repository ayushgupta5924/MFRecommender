import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../auth";
import { COMPLIANCE } from "../constants/compliance";
import { ThemePicker } from "../theme";

function initials(name) {
  const parts = (name || "").trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

export function BrandMark() {
  return (
    <svg className="brandMark" viewBox="0 0 64 64" aria-hidden="true">
      <defs>
        <linearGradient id="brandLine" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--accent-text)" />
          <stop offset="1" stopColor="var(--accent)" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="var(--surface-2)" stroke="var(--border-strong)" />
      <path d="M14 46 L26 33 L35 40 L50 20" fill="none" stroke="url(#brandLine)" strokeWidth="6"
        strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="50" cy="20" r="5" fill="#d4af37" />
    </svg>
  );
}

export default function AppBar({ title, onBack, extra }) {
  const { user, accountsEnabled } = useAuth();
  return (
    <header className="appBar">
      <div className="appBar__inner">
        {onBack && <button className="backBtn" aria-label="Back" onClick={onBack}>←</button>}
        {onBack && title ? (
          <>
            <Link to="/" className="appBar__brand appBar__brand--mark" aria-label="Home"><BrandMark /></Link>
            <span className="appBar__title">{title}</span>
          </>
        ) : (
          <>
            <Link to="/" className="appBar__brand" aria-label="Home">
              <BrandMark />
              <span className="appBar__brandName">{COMPLIANCE.brandName}</span>
            </Link>
            <span className="appBar__spacer" />
          </>
        )}
        {extra}
        <nav className="appBar__nav">
          <NavLink to="/plan" end className="appBar__link appBar__link--hideSm">Plan</NavLink>
          <NavLink to="/review" className="appBar__link">Review</NavLink>
          <NavLink to="/how-advice-works" className="appBar__link appBar__link--hideSm">How it works</NavLink>
          <ThemePicker />
          {user && (
            <NavLink to="/account" className="appBar__avatar" title={user.full_name} aria-label="Your account">
              {initials(user.full_name)}
            </NavLink>
          )}
          {accountsEnabled && user === null && <NavLink to="/login" className="appBar__link appBar__link--solid">Log in</NavLink>}
        </nav>
      </div>
    </header>
  );
}
