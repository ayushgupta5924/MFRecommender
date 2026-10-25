import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, RequireAuth } from "./auth";
import AccountScreen from "./components/AccountScreen";
import AuthScreen from "./components/AuthScreen";
import Footer from "./components/Footer";
import FundScreen from "./components/FundScreen";
import FundsScreen from "./components/FundsScreen";
import InfoScreen from "./components/InfoScreen";
import InputScreen from "./components/InputScreen";
import ComplaintsScreen from "./components/ComplaintsScreen";
import HowAdviceWorksScreen from "./components/HowAdviceWorksScreen";
import InvestorCharterScreen from "./components/InvestorCharterScreen";
import PrivacyScreen from "./components/PrivacyScreen";
import ResultsScreen from "./components/ResultsScreen";
import ReviewScreen from "./components/ReviewScreen";
import { usePageMeta } from "./utils/meta";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

// Titles for screens that don't set their own (the home page and fund pages do).
const TITLES = {
  "/plan": "Build your plan",
  "/plan/results": "Your plan",
  "/review": "Portfolio review",
  "/login": "Log in",
  "/signup": "Create account",
  "/account": "Your account",
  "/investor-charter": "Investor Charter",
  "/complaints": "Complaints data",
  "/how-advice-works": "How our advice works",
  "/privacy": "Privacy Notice",
};

function RouteMeta() {
  const { pathname } = useLocation();
  usePageMeta(TITLES[pathname] ?? null);
  return null;
}

function Meta() {
  const { pathname } = useLocation();
  return pathname === "/" || pathname.startsWith("/fund") ? null : <RouteMeta key={pathname} />;
}

// Every screen has its own URL, so a refresh or a shared link opens the same screen.
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ScrollToTop />
        <Meta />
        <Routes>
          <Route path="/" element={<InfoScreen />} />
          <Route path="/plan" element={<InputScreen />} />
          <Route path="/plan/results" element={<ResultsScreen />} />
          <Route path="/login" element={<AuthScreen mode="login" key="login" />} />
          <Route path="/signup" element={<AuthScreen mode="signup" key="signup" />} />
          <Route path="/investor-charter" element={<InvestorCharterScreen />} />
          <Route path="/complaints" element={<ComplaintsScreen />} />
          <Route path="/how-advice-works" element={<HowAdviceWorksScreen />} />
          <Route path="/privacy" element={<PrivacyScreen />} />
          <Route path="/review" element={<ReviewScreen />} />
          <Route path="/funds" element={<FundsScreen />} />
          <Route path="/fund/:code" element={<FundScreen />} />
          <Route path="/account" element={<RequireAuth><AccountScreen /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Footer />
      </AuthProvider>
    </BrowserRouter>
  );
}
