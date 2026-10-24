import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, RequireAuth } from "./auth";
import AccountScreen from "./components/AccountScreen";
import AuthScreen from "./components/AuthScreen";
import Footer from "./components/Footer";
import InfoScreen from "./components/InfoScreen";
import InputScreen from "./components/InputScreen";
import ComplaintsScreen from "./components/ComplaintsScreen";
import HowAdviceWorksScreen from "./components/HowAdviceWorksScreen";
import InvestorCharterScreen from "./components/InvestorCharterScreen";
import PrivacyScreen from "./components/PrivacyScreen";
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
          <Route path="/complaints" element={<ComplaintsScreen />} />
          <Route path="/how-advice-works" element={<HowAdviceWorksScreen />} />
          <Route path="/privacy" element={<PrivacyScreen />} />
          <Route path="/review" element={<ReviewScreen />} />
          <Route path="/account" element={<RequireAuth><AccountScreen /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Footer />
      </AuthProvider>
    </BrowserRouter>
  );
}
