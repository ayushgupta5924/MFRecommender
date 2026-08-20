import { useState } from "react";
import InfoScreen from "./components/InfoScreen";
import InputScreen from "./components/InputScreen";
import ResultsScreen from "./components/ResultsScreen";

export default function App() {
  const [screen, setScreen] = useState("info");
  const [results, setResults] = useState(null);
  const [budget, setBudget] = useState(0);

  const handleResults = (data, b) => {
    setResults(data);
    setBudget(data?.monthly_sip_required || b || 0);
    setScreen("results");
  };

  return (
    <>
      {screen === "info" && (
        <InfoScreen onNext={() => setScreen("input")} />
      )}
      {screen === "input" && (
        <InputScreen
          onBack={() => setScreen("info")}
          onResults={handleResults}
        />
      )}
      {screen === "results" && (
        <ResultsScreen
          onBack={() => setScreen("input")}
          results={results}
          budget={budget}
        />
      )}
    </>
  );
}