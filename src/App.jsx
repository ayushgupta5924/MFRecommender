import { useEffect, useState } from "react";
import { warmUp } from "./api";
import Footer from "./components/Footer";
import InfoScreen from "./components/InfoScreen";
import InputScreen from "./components/InputScreen";
import ResultsScreen from "./components/ResultsScreen";

export default function App() {
  const [screen, setScreen] = useState("info");
  const [results, setResults] = useState(null);

  // Wake the backend while the user reads the intro.
  useEffect(() => { warmUp(); }, []);

  useEffect(() => { window.scrollTo(0, 0); }, [screen]);

  const handleResults = (data) => {
    setResults(data);
    setScreen("results");
  };

  return (
    <>
      {screen === "info" && (
        <InfoScreen onNext={() => setScreen("input")} />
      )}
      {/* Kept mounted so answers survive "Adjust Profile". */}
      <div hidden={screen !== "input"}>
        <InputScreen
          onBack={() => setScreen("info")}
          onResults={handleResults}
        />
      </div>
      {screen === "results" && results && (
        <ResultsScreen
          onBack={() => setScreen("input")}
          results={results}
        />
      )}
      <Footer />
    </>
  );
}
