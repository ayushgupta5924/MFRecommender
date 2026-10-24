import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { getHealth, getMe, logout as apiLogout } from "./api";
import { clearPlanData } from "./utils/storage";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // undefined while we ask the server, then a user object or null.
  const [user, setUser] = useState(undefined);
  // Whether the backend has accounts switched on (database and email configured).
  const [accountsEnabled, setAccountsEnabled] = useState(undefined);

  useEffect(() => {
    getHealth().then((h) => setAccountsEnabled(!!h.accounts_enabled)).catch(() => setAccountsEnabled(false));
    getMe().then(setUser).catch(() => setUser(null));
  }, []);

  const logout = useCallback(async () => {
    // Someone else may use this browser next: don't leave financial answers behind.
    try { await apiLogout(); } finally { clearPlanData(); setUser(null); }
  }, []);

  return <AuthContext.Provider value={{ user, setUser, logout, accountsEnabled }}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext);
}

export function ComingSoon() {
  return (
    <div className="page">
      <div className="body comingSoon">
        <div className="comingSoon__icon">🛠️</div>
        <div className="stepTitle">Accounts and portfolio review are coming soon</div>
        <div className="stepSubtitle">Meanwhile you can build a plan without an account.</div>
        <Link className="btnBlue" to="/plan">Build my plan →</Link>
      </div>
    </div>
  );
}

// Sends logged-out visitors to /login and brings them back here afterwards.
export function RequireAuth({ children }) {
  const { user, accountsEnabled } = useAuth();
  const location = useLocation();
  if (accountsEnabled === false) return <ComingSoon />;
  if (user === undefined || accountsEnabled === undefined) return <div className="pageLoading">Loading…</div>;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  return children;
}
