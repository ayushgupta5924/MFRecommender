import { useEffect, useState } from "react";

// Colour themes (tokens in styles/theme.css). index.html applies the saved one before the first paint.
const THEMES = [
  { key: "midnight", label: "Midnight", swatch: ["#060a13", "#3b82f6"] },
  { key: "gold", label: "Gold", swatch: ["#080706", "#d4af37"] },
  { key: "daylight", label: "Daylight", swatch: ["#ffffff", "#60a5fa"] },
];
const KEY = "mfa:theme";
const META_COLOR = { midnight: "#060a13", gold: "#080706", daylight: "#f3f7fd" };

// index.html has already picked it (from ?theme= or storage) and set it on <html>.
function savedTheme() {
  const t = document.documentElement.dataset.theme;
  return THEMES.some((x) => x.key === t) ? t : "midnight";
}

function apply(theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", META_COLOR[theme]);
}

export function ThemePicker() {
  const [theme, setTheme] = useState(savedTheme);
  useEffect(() => {
    apply(theme);
    try { localStorage.setItem(KEY, theme); } catch { /* storage blocked */ }
  }, [theme]);

  return (
    <div className="themePicker" role="radiogroup" aria-label="Colour theme">
      {THEMES.map((t) => (
        <button key={t.key} type="button" role="radio" aria-checked={theme === t.key} title={t.label}
          aria-label={`${t.label} theme`} className={`themeDot ${theme === t.key ? "themeDot--on" : ""}`}
          style={{ background: `linear-gradient(135deg, ${t.swatch[0]} 0 50%, ${t.swatch[1]} 50% 100%)` }}
          onClick={() => setTheme(t.key)} />
      ))}
    </div>
  );
}
