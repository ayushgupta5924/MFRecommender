import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { getMe, logout as apiLogout } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // undefined while we ask the server, then a user object or null.
  const [user, setUser] = useState(undefined);

  useEffect(() => {
    getMe().then(setUser).catch(() => setUser(null));
  }, []);

  const logout = useCallback(async () => {
    try { await apiLogout(); } finally { setUser(null); }
  }, []);

  return <AuthContext.Provider value={{ user, setUser, logout }}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext);
}

// Sends logged-out visitors to /login and brings them back here afterwards.
export function RequireAuth({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (user === undefined) return <div className="pageLoading">Loading…</div>;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  return children;
}
