import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, RequireAuth } from "./auth";
import AccountScreen from "./components/AccountScreen";
import AuthScreen from "./components/AuthScreen";
import Footer from "./components/Footer";
import InfoScreen from "./components/InfoScreen";
import InputScreen from "./components/InputScreen";
import InvestorCharterScreen from "./components/InvestorCharterScreen";
import ResultsScreen from "./components/ResultsScreen";
import ReviewScreen from "./components/ReviewScreen";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

// Every screen has its own URL, so a refresh or a shared link opens the same screen.
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ScrollToTop />
        <Routes>
          <Route path="/" element={<InfoScreen />} />
          <Route path="/plan" element={<InputScreen />} />
          <Route path="/plan/results" element={<ResultsScreen />} />
          <Route path="/login" element={<AuthScreen mode="login" key="login" />} />
          <Route path="/signup" element={<AuthScreen mode="signup" key="signup" />} />
          <Route path="/investor-charter" element={<InvestorCharterScreen />} />
          <Route path="/review" element={<RequireAuth><ReviewScreen /></RequireAuth>} />
          <Route path="/account" element={<RequireAuth><AccountScreen /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Footer />
      </AuthProvider>
    </BrowserRouter>
  );
}
