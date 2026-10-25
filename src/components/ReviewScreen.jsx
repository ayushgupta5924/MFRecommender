import { useEffect, useMemo, useState } from "react";
import { Banknote, CircleCheck, FileText, IdCard, Info, Lock, OctagonAlert, PenLine, RefreshCw, Smartphone, TriangleAlert } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { COMPLIANCE } from "../constants/compliance";
import { STATUS_LABEL } from "../constants/ratings";
import {
  aaStatus, addHolding, deleteReview, getReview, guestReview, guestUpload, panStatus, removeHolding, searchFunds,
  startAaFetch, startPanFetch, uploadStatement,
} from "../api";
import "../styles/InputScreen.css";
import "../styles/ResultsScreen.css";
import "../styles/ReviewScreen.css";
import "../styles/shared.css";
import { fmt, fmtDate } from "../utils/format";
import { AA_PENDING_KEY, GUEST_REVIEW_KEY, loadSession, saveSession } from "../utils/storage";
import AppBar from "./AppBar";
import Disclaimer from "./Disclaimer";

const CAS_URL = "https://www.camsonline.com/Investors/Statements/Consolidated-Account-Statement";
const SLEEVES = [["equity", "Equity", "var(--mix-equity)"], ["hybrid", "Hybrid", "var(--mix-hybrid)"], ["debt", "Debt", "var(--mix-debt)"],
  ["other", "Gold & other", "var(--mix-other)"]];
const STATUS_ORDER = ["in_form", "on_track", "off_track", "out_of_form", "not_rated"];
const LEVEL_ICON = { high: OctagonAlert, medium: TriangleAlert, low: Info, good: CircleCheck };
const AA_POLL_MS = 3000;
const AA_WAIT_MS = 3 * 60 * 1000;     // registrars usually answer within a minute
const PAN_POLL_MS = 3000;
const PAN_WAIT_MS = 3 * 60 * 1000;    // MF Central usually sends the holdings within a minute of the OTP

function InsightIcon({ level }) {
  const Icon = LEVEL_ICON[level] || Info;
  return <Icon size={16} className={`insight__icon insight__icon--${level}`} />;
}

// Fractions from the API (0.123) to "12.3%".
const pctF = (v, digits = 1) => (v == null ? "—" : `${v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(digits)}%`);
const signed = (n) => (n == null ? "—" : `${n < 0 ? "−" : "+"}${fmt(Math.abs(n))}`);

// ── Where the portfolio lives ───────────────────────────────────────────────
// Logged in: on the server, in the account. Guest: only in this browser tab, sent to the server for each review.

const accountSource = {
  guest: false,
  load: getReview,
  upload: uploadStatement,
  add: addHolding,
  remove: removeHolding,
  clear: async () => { await deleteReview(); return { empty: true }; },
  fetchDone: (r) => r.review,                // already saved to the account
};

function keepGuest(r, statement) {
  // `funds` (one row per scheme, valued) is what the plan questionnaire offers to use.
  const funds = r.review.holdings.map(({ code, name, units, value }) => ({ code, name, units, value }));
  const kept = { holdings: r.holdings, funds, statement: r.statement || statement || null };
  saveSession(GUEST_REVIEW_KEY, kept);
  return { ...r.review, statement: kept.statement, parse_warnings: r.parse_warnings, fetch_warnings: r.fetch_warnings };
}

const guestSource = {
  guest: true,
  load: async () => {
    const saved = loadSession(GUEST_REVIEW_KEY, null);
    if (!saved?.holdings?.length) return { empty: true };
    return keepGuest(await guestReview(saved.holdings), saved.statement);
  },
  upload: async (file, password, consent) => {
    // A new statement replaces the previous one; funds added by hand stay.
    const manual = (loadSession(GUEST_REVIEW_KEY, null)?.holdings || []).filter((h) => h.source === "manual");
    const r = await guestUpload(file, password, consent);
    if (!manual.length) return keepGuest(r);
    return { ...keepGuest(await guestReview([...r.holdings, ...manual]), r.statement), parse_warnings: r.parse_warnings };
  },
  add: async ({ code, units, value, invested }) => {
    const saved = loadSession(GUEST_REVIEW_KEY, null);
    return keepGuest(await guestReview(saved?.holdings || [], { code, units, value, invested }), saved?.statement);
  },
  remove: async (id) => {
    const saved = loadSession(GUEST_REVIEW_KEY, null);
    const rest = (saved?.holdings || []).filter((h) => h.id !== id);
    if (!rest.length) return guestSource.clear();
    return keepGuest(await guestReview(rest), saved.statement);
  },
  clear: async () => { saveSession(GUEST_REVIEW_KEY, undefined); return { empty: true }; },
  // Fetched funds replace an earlier import, like a new statement; funds added by hand stay.
  fetchDone: async (r) => {
    const manual = (loadSession(GUEST_REVIEW_KEY, null)?.holdings || []).filter((h) => h.source === "manual");
    if (!manual.length) return keepGuest(r);
    return { ...keepGuest(await guestReview([...r.holdings, ...manual]), r.statement), fetch_warnings: r.fetch_warnings };
  },
};

// ── Import: CAS upload or manual entry ──────────────────────────────────────

// Consent to use the holdings (required) and, with an account, the alerts opt-in (optional), shown before any import.
function ImportConsent({ consent, setConsent, alerts, setAlerts, guest }) {
  const { user } = useAuth();
  return (
    <div className="importConsent">
      <label className="consentRow">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        {guest ? (
          <span>
            I agree to {COMPLIANCE.brandName} reading my fund holdings and transactions to review them, and keeping a
            record of the review as SEBI requires, as described in the{" "}
            <Link to="/privacy" target="_blank">Privacy Notice</Link>.
          </span>
        ) : (
          <span>
            I agree to {COMPLIANCE.brandName} storing my fund holdings and transactions to review them, as described in the{" "}
            <Link to="/privacy" target="_blank">Privacy Notice</Link>.
          </span>
        )}
      </label>
      {!guest && !user?.alerts_enabled && (
        <label className="consentRow">
          <input type="checkbox" checked={alerts} onChange={(e) => setAlerts(e.target.checked)} />
          <span>Email me when a fund I hold changes rating (at most once a month). Optional.</span>
        </label>
      )}
    </div>
  );
}

function useImportConsent() {
  const { user, setUser } = useAuth();
  const [consent, setConsent] = useState(false);
  const [alerts, setAlerts] = useState(false);
  const afterImport = () => { if (alerts && user) setUser({ ...user, alerts_enabled: true }); };
  return { consent, setConsent, alerts, setAlerts, afterImport };
}

function UploadStatement({ source, onDone }) {
  const c = useImportConsent();
  const [file, setFile] = useState(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const result = await source.upload(file, password, c.consent, c.alerts);
      c.afterImport();
      onDone(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <ol className="casSteps">
        <li>Open the <a href={CAS_URL} target="_blank" rel="noreferrer">CAMS statement page</a> and choose
          <b> CAS – CAMS + KFintech</b>. It covers funds from every fund house.</li>
        <li>Pick <b>Detailed</b>, set the period to <b>Since inception</b>, enter your email and choose a password.</li>
        <li>The PDF reaches your inbox in a few minutes. Upload it here with that password.</li>
      </ol>
      <div className="fieldWrap">
        <label className="fieldLabel" htmlFor="cas">Statement PDF</label>
        <input id="cas" type="file" accept="application/pdf,.pdf" className="fileInput"
          onChange={(e) => setFile(e.target.files?.[0] || null)} />
      </div>
      <div className="fieldWrap">
        <label className="fieldLabel" htmlFor="pw">PDF password</label>
        <input id="pw" type="password" className="fieldInput plainInput" value={password} autoComplete="off"
          onChange={(e) => setPassword(e.target.value)} placeholder="The password you set when requesting it" />
      </div>
      <ImportConsent {...c} guest={source.guest} />
      <button className="btnBlue" type="submit" disabled={busy || !file || !c.consent}>
        {busy ? "Reading your statement…" : "Review my portfolio"}
      </button>
      {error && <div className="errorText">{error}</div>}
      <div className="mutedText privacyNote">
        <Lock size={13} className="ico" /> We read the funds, units and transactions, then discard the file. Your PAN, address, phone and the PDF
        itself are never stored.{" "}
        {source.guest
          ? "Without an account your holdings stay in this browser tab and are gone when you close it."
          : "You can delete your portfolio at any time."}{" "}
        A record of the advice we give is kept for 5 years, as SEBI requires.
      </div>
    </form>
  );
}

// One-time, read-only consent through an Account Aggregator. The AA asks for the PAN, so we never see it.
function FetchByMobile({ source }) {
  const c = useImportConsent();
  const [mobile, setMobile] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const valid = /^[6-9]\d{9}$/.test(mobile);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const r = await startAaFetch(mobile, c.consent, c.alerts);
      saveSession(AA_PENDING_KEY, { id: r.id, key: r.key });
      c.afterImport();
      window.location.assign(r.url);       // the AA's consent screens; they send the investor back to /review
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <ol className="casSteps">
        <li>Enter the mobile number linked to your mutual funds (the one in your KYC).</li>
        <li>You'll go to an RBI-licensed Account Aggregator. It asks for your PAN to find your funds, and you approve a
          one-time, <b>read-only</b> consent with an OTP.</li>
        <li>You come straight back here to your review. We withdraw the consent as soon as the data arrives.</li>
      </ol>
      <div className="fieldWrap">
        <label className="fieldLabel" htmlFor="aaMobile">Mobile number</label>
        <input id="aaMobile" type="tel" inputMode="numeric" maxLength={10} autoComplete="tel-national"
          className="fieldInput plainInput" value={mobile} placeholder="10-digit mobile number"
          onChange={(e) => setMobile(e.target.value.replace(/\D/g, ""))} />
        {mobile.length === 10 && !valid && <div className="fieldHint fieldHint--error">Enter a valid Indian mobile number.</div>}
      </div>
      <ImportConsent {...c} guest={source.guest} />
      <button className="btnBlue" type="submit" disabled={busy || !valid || !c.consent}>
        {busy ? "Opening the Account Aggregator…" : "Fetch my funds"}
      </button>
      {error && <div className="errorText">{error}</div>}
      <div className="mutedText privacyNote">
        <Lock size={13} className="ico" /> Read-only: nobody can buy, sell or move money with this consent. We never see your PAN, don't keep your
        mobile number, and ask only for your funds and their transactions.{" "}
        {source.guest
          ? "Without an account your holdings stay in this browser tab and are gone when you close it."
          : "You can delete your portfolio at any time."}
      </div>
    </form>
  );
}

// smallcase's SDK, loaded only when someone fetches by PAN.
function loadScript(src) {
  if (window.scDK) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("We couldn't load MF Central's sign-in window. Check your connection and try again."));
    document.body.appendChild(s);
  });
}

const PAN_RE = /^[A-Z]{5}\d{4}[A-Z]$/;
const MOBILE_RE = /^[6-9]\d{9}$/;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// Read-only fetch from MF Central by PAN. MF Central sends an OTP to the mobile or email registered with the funds,
// and the investor enters it in smallcase's window, so only they can fetch them.
function FetchByPan({ source, onDone }) {
  const c = useImportConsent();
  const [pan, setPan] = useState("");
  const [contact, setContact] = useState("");
  const [stage, setStage] = useState("");          // "" | "otp" | "fetching"
  const [error, setError] = useState("");
  const isEmail = contact.includes("@");
  const contactOk = isEmail ? EMAIL_RE.test(contact) : MOBILE_RE.test(contact);
  const valid = PAN_RE.test(pan) && contactOk;

  const waitForHoldings = async (id, key) => {
    const until = Date.now() + PAN_WAIT_MS;
    while (Date.now() < until) {
      const r = await panStatus(id, key);
      if (r.status === "done" && (r.review || r.holdings)) return r;
      if (r.status === "failed") throw new Error(r.message);
      if (r.status === "done") throw new Error("These holdings were already fetched. Please start again.");
      await new Promise((ok) => setTimeout(ok, PAN_POLL_MS));
    }
    throw new Error("MF Central is taking longer than usual. Please try again in a few minutes, or upload your statement.");
  };

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setStage("otp");
    try {
      const start = await startPanFetch(pan, isEmail ? { email: contact } : { mobile: contact }, c.consent, c.alerts);
      await loadScript(start.sdk);
      const gateway = new window.scDK({ gateway: start.gateway, smallcaseAuthToken: start.token });
      try {
        await gateway.triggerTransaction({ transactionId: start.id });
      } catch {
        throw new Error("The MF Central window was closed before your funds were fetched, so nothing was imported.");
      }
      setStage("fetching");
      const r = await waitForHoldings(start.id, start.key);
      c.afterImport();
      onDone(await source.fetchDone(r));
    } catch (err) {
      setError(err.message);
      setStage("");
    }
  };

  return (
    <form onSubmit={submit}>
      <ol className="casSteps">
        <li>Enter your PAN and the mobile number or email registered with your mutual funds.</li>
        <li>MF Central (run by CAMS and KFintech) sends a one-time password there. Enter it in the window that opens.</li>
        <li>Your funds from every fund house come straight into your review.</li>
      </ol>
      <div className="fieldWrap">
        <label className="fieldLabel" htmlFor="panNo">PAN</label>
        <input id="panNo" maxLength={10} autoComplete="off" spellCheck={false}
          className="fieldInput plainInput" value={pan} placeholder="ABCDE1234F"
          onChange={(e) => setPan(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))} />
        {pan.length === 10 && !PAN_RE.test(pan) && <div className="fieldHint fieldHint--error">That isn't a valid PAN.</div>}
      </div>
      <div className="fieldWrap">
        <label className="fieldLabel" htmlFor="panContact">Mobile number or email registered with your funds</label>
        <input id="panContact" autoComplete="off" className="fieldInput plainInput" value={contact}
          placeholder="10-digit mobile or email" onChange={(e) => setContact(e.target.value.trim())} />
        {contact.length >= 10 && !contactOk && (
          <div className="fieldHint fieldHint--error">Enter a 10-digit Indian mobile number or an email address.</div>
        )}
      </div>
      <ImportConsent {...c} guest={source.guest} />
      <button className="btnBlue" type="submit" disabled={!!stage || !valid || !c.consent}>
        {stage === "otp" ? "Waiting for the OTP…" : stage === "fetching" ? "Fetching your funds…" : "Fetch my funds"}
      </button>
      {error && <div className="errorText">{error}</div>}
      <div className="mutedText privacyNote">
        <Lock size={13} className="ico" /> Read-only: this can't buy, sell or move anything. Your PAN and contact are sent to MF Central (through our
        technology partner smallcase) only to find your funds; we don't keep them, or your name, address or bank
        details. We keep fund-level data only.{" "}
        {source.guest
          ? "Without an account your holdings stay in this browser tab and are gone when you close it."
          : "You can delete your portfolio at any time."}
      </div>
    </form>
  );
}

function AddFund({ source, onDone }) {
  const c = useImportConsent();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);
  const [fund, setFund] = useState(null);
  const [mode, setMode] = useState("value");
  const [amount, setAmount] = useState("");
  const [invested, setInvested] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (fund || q.trim().length < 3) return undefined;
    let live = true;
    const t = setTimeout(() => {
      searchFunds(q.trim()).then((r) => live && setHits(r)).catch(() => live && setHits([]));
    }, 300);
    return () => { live = false; clearTimeout(t); };
  }, [q, fund]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const body = { code: fund.code, invested: invested ? Number(invested) : null, consent: c.consent, alerts: c.alerts };
      body[mode === "units" ? "units" : "value"] = Number(amount);
      const result = await source.add(body);
      c.afterImport();
      onDone(result);
      setFund(null); setQ(""); setAmount(""); setInvested(""); setHits([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (!fund) {
    return (
      <div>
        <div className="fieldWrap">
          <label className="fieldLabel" htmlFor="fundq">Search for a fund</label>
          <input id="fundq" className="fieldInput plainInput" value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. Parag Parikh Flexi Cap" autoComplete="off" />
        </div>
        {q.trim().length >= 3 && (
          <div className="fundHits">
            {hits.length === 0 && <div className="mutedText">No matching funds yet. Try fewer words.</div>}
            {hits.map((h) => (
              <button type="button" key={h.code} className="fundHit" onClick={() => setFund(h)}>
                <span className="fundHit__name">{h.name}</span>
                <span className="fundHit__meta">{h.plan} · {h.option} · {h.amc}</span>
              </button>
            ))}
          </div>
        )}
        <div className="mutedText">Check your statement or app for whether you hold the Direct or Regular plan.</div>
      </div>
    );
  }

  return (
    <form onSubmit={submit}>
      <div className="pickedFund">
        <div>
          <div className="fundHit__name">{fund.name}</div>
          <div className="fundHit__meta">{fund.plan} · {fund.option} · {fund.amc}</div>
        </div>
        <button type="button" className="linkBtn" onClick={() => setFund(null)}>Change</button>
      </div>
      <div className="quizOptions" style={{ marginBottom: 12 }}>
        {[["value", "I know its current value"], ["units", "I know the units"]].map(([v, l]) => (
          <button type="button" key={v} className={`quizOption ${mode === v ? "quizOption--selected" : ""}`}
            onClick={() => setMode(v)}>{l}</button>
        ))}
      </div>
      <div className="fieldWrap">
        <label className="fieldLabel" htmlFor="amt">{mode === "units" ? "Units held" : "Current value (₹)"}</label>
        <input id="amt" type="number" min="0" step="any" className="fieldInput plainInput" value={amount}
          onChange={(e) => setAmount(e.target.value)} required />
      </div>
      <div className="fieldWrap">
        <label className="fieldLabel" htmlFor="inv">Amount you invested (₹, optional)</label>
        <input id="inv" type="number" min="0" step="any" className="fieldInput plainInput" value={invested}
          onChange={(e) => setInvested(e.target.value)} />
      </div>
      <ImportConsent {...c} guest={source.guest} />
      <button className="btnBlue" type="submit" disabled={busy || !(Number(amount) > 0) || !c.consent}>
        {busy ? "Adding…" : "Add fund"}
      </button>
      {error && <div className="errorText">{error}</div>}
    </form>
  );
}

function ImportPanel({ source, onDone, onCancel }) {
  const { aaEnabled, panEnabled } = useAuth();
  const [tab, setTab] = useState(panEnabled ? "pan" : aaEnabled ? "aa" : "upload");
  const tabs = [panEnabled && ["pan", IdCard, "Fetch with PAN"], aaEnabled && ["aa", Smartphone, "Fetch with mobile"],
    ["upload", FileText, "Upload statement"], ["manual", PenLine, "Add by hand"]];
  return (
    <div className="card">
      <div className="importTabs">
        {tabs.filter(Boolean).map(([k, Icon, label]) => (
          <button key={k} className={`importTab ${tab === k ? "importTab--on" : ""}`} onClick={() => setTab(k)}>
            <Icon size={16} /> {label}
          </button>
        ))}
      </div>
      {tab === "pan" && <FetchByPan source={source} onDone={onDone} />}
      {tab === "aa" && <FetchByMobile source={source} />}
      {tab === "upload" && <UploadStatement source={source} onDone={onDone} />}
      {tab === "manual" && <AddFund source={source} onDone={onDone} />}
      {onCancel && <button className="linkBtn cancelImport" onClick={onCancel}>Cancel</button>}
    </div>
  );
}

// ── Review ──────────────────────────────────────────────────────────────────

function Summary({ data }) {
  const s = data.summary;
  return (
    <div className="reviewHero">
      <div className="reviewHero__label">Current value</div>
      <div className="reviewHero__value">{fmt(s.value)}</div>
      <div className="reviewHero__grid">
        <div><span>Invested</span><b>{fmt(s.invested)}</b></div>
        <div><span>Gain</span><b>{signed(s.gain)}{s.gain_pct != null && ` (${s.gain_pct.toFixed(1)}%)`}</b></div>
        <div><span>XIRR</span><b>{s.xirr != null ? `${pctF(s.xirr)} a year` : "—"}</b></div>
        <div><span>Funds</span><b>{s.funds}</b></div>
      </div>
      {s.invested != null && s.funds_with_cost < s.funds && (
        <div className="reviewHero__note">
          Invested and gain cover {s.funds_with_cost} of {s.funds} funds; add the amount invested to the others to include them.
        </div>
      )}
    </div>
  );
}

function Health({ health }) {
  const counts = health.by_status || {};
  return (
    <div className="card">
      <div className="card__title">Fund health</div>
      {health.good_pct != null && (
        <div className="healthLine">
          <span className="healthLine__pct">{Math.round(health.good_pct)}%</span>
          of the money in rated funds is in funds in the <b>top half</b> of their category.
        </div>
      )}
      <div className="statusChips">
        {STATUS_ORDER.filter((k) => counts[k]?.count).map((k) => (
          <span key={k} className={`statusChip statusChip--${k}`}>{STATUS_LABEL[k]}: {counts[k].count}</span>
        ))}
      </div>
      <div className="mutedText" style={{ marginTop: 10 }}>
        Each fund is compared with every other fund in its category on returns, consistency (rolling returns),
        how far it fell in bad markets, its record against its index, its expense ratio and whether its size suits
        the category, and rated by quarter: Top 25%, Above average, Below average or Bottom 25%.
      </div>
    </div>
  );
}

function Allocation({ allocation, target }) {
  return (
    <div className="card">
      <div className="card__title">Asset mix</div>
      <div className="mixBar" role="img" aria-label="Your asset mix">
        {SLEEVES.filter(([k]) => allocation[k] > 0).map(([k, , c]) => (
          <div key={k} className="mixBar__seg" style={{ width: `${allocation[k]}%`, background: c }} />
        ))}
      </div>
      <div className="mixLegend">
        {SLEEVES.filter(([k]) => allocation[k] > 0).map(([k, label, c]) => (
          <span key={k} className="mixLegend__item"><span className="mixLegend__dot" style={{ background: c }} />{label} {Math.round(allocation[k])}%</span>
        ))}
      </div>
      {target?.asset_mix ? (
        <div className="targetLine">
          Your saved plan <b>{target.name}</b> aims for {Math.round(target.asset_mix.equity)}% equity,{" "}
          {Math.round(target.asset_mix.hybrid)}% hybrid and {Math.round(target.asset_mix.debt)}% debt.
        </div>
      ) : (
        <div className="targetLine">
          <Link to="/plan">Build and save a plan</Link> to compare this mix with what suits your goal and risk profile.
        </div>
      )}
    </div>
  );
}

function Insights({ insights }) {
  if (!insights.length) return null;
  return (
    <div className="card">
      <div className="card__title">What to look at</div>
      {insights.map((i) => (
        <div key={i.key} className={`insight insight--${i.level}`}>
          <div className="insight__title"><InsightIcon level={i.level} /> {i.title}</div>
          <div className="insight__text">{i.text}</div>
        </div>
      ))}
    </div>
  );
}

// Look-through: the companies the money is really in, and funds that own the same stocks.
function LookThrough({ stocks, overlaps }) {
  if (!stocks?.length) return null;
  return (
    <div className="card">
      <div className="card__title">Where your equity money really is</div>
      <table className="metricTable">
        <thead><tr><th>Company</th><th>Share of fund money</th><th>Held by</th></tr></thead>
        <tbody>
          {stocks.map((s) => (
            <tr key={s.name}><td>{s.name}</td><td>{s.pct != null ? `${s.pct.toFixed(1)}%` : "—"}</td><td>{s.funds} fund{s.funds > 1 ? "s" : ""}</td></tr>
          ))}
        </tbody>
      </table>
      {overlaps?.length > 0 && (
        <>
          <div className="card__subtitle">Overlap between your funds</div>
          {overlaps.slice(0, 5).map((o) => (
            <div key={`${o.a}|${o.b}`} className="overlapRow">
              <span>{o.a} &amp; {o.b}</span>
              <b className={o.pct >= 40 ? "neg" : ""}>{Math.round(o.pct)}% the same</b>
            </div>
          ))}
        </>
      )}
      <div className="mutedText" style={{ marginTop: 10 }}>
        From each fund&apos;s latest monthly portfolio disclosure. Overlap is the share of two funds&apos; money in the
        same stocks; above 40% they behave much like one fund.
      </div>
    </div>
  );
}

function Tax({ tax }) {
  if (!tax.lt_gain && !tax.st_gain && !tax.elss_locked) return null;
  return (
    <div className="card">
      <div className="card__title">Tax view (equity funds)</div>
      <div className="taxGrid">
        <div><span>Long-term gains</span><b>{signed(tax.lt_gain)}</b><small>held over 1 year</small></div>
        <div><span>Short-term gains</span><b>{signed(tax.st_gain)}</b><small>held 1 year or less</small></div>
        {tax.elss_locked > 0 && <div><span>ELSS locked in</span><b>{fmt(tax.elss_locked)}</b><small>under 3 years old</small></div>}
      </div>
      <div className="mutedText" style={{ marginTop: 10 }}>
        Up to {fmt(tax.ltcg_exemption)} of long-term equity gains a year is tax-free. If you haven't booked other
        gains this year, selling and reinvesting up to that amount resets your cost and can lower tax later.
        Debt fund gains are taxed at your income-tax slab. These are unrealised gains on what you hold now, not a tax
        calculation{!tax.complete && "; some funds are missing because the statement doesn't start at your first investment"}.
      </div>
    </div>
  );
}

function HoldingCard({ h, onRemove }) {
  const [open, setOpen] = useState(false);
  const r = h.rating;
  const m = r.metrics || {};
  const c = r.category || {};
  return (
    <div className={`holding holding--${r.status}`}>
      <button type="button" className="holding__head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <div className="holding__main">
          <div className="holding__name">{h.name}</div>
          <div className="holding__meta">
            {h.category} · <span className={h.plan === "Regular" ? "tagWarn" : ""}>{h.plan}</span>
            {h.option === "IDCW" && <> · <span className="tagWarn">IDCW</span></>}
            {h.source === "manual" && " · added by hand"}
          </div>
        </div>
        <div className="holding__right">
          <span className={`statusChip statusChip--${r.status}`}>{r.label}</span>
          <div className="holding__value">{fmt(h.value)}</div>
          <div className={`holding__gain ${h.gain < 0 ? "neg" : ""}`}>
            {h.gain != null ? signed(h.gain) : ""}{h.xirr != null ? ` · ${pctF(h.xirr)} XIRR` : ""}
          </div>
        </div>
      </button>
      {open && (
        <div className="holding__body">
          <div className="holding__action"><b>{r.status === "not_rated" ? "Why no rating: " : "What to do: "}</b>{h.action.text}</div>
          {r.status !== "not_rated" && <div className="mutedText">{r.reason}</div>}
          {r.metrics && (
            <table className="metricTable">
              <thead><tr><th></th><th>This fund</th><th>Category median</th></tr></thead>
              <tbody>
                <tr><td>1-year return</td><td>{pctF(m.cagr_1y)}</td><td>{pctF(c.cagr_1y)}</td></tr>
                <tr><td>3-year return (a year)</td><td>{pctF(m.cagr_3y)}</td><td>{pctF(c.cagr_3y)}</td></tr>
                <tr><td>5-year return (a year)</td><td>{pctF(m.cagr_5y)}</td><td>{pctF(c.cagr_5y)}</td></tr>
                <tr><td>Worst fall</td><td>{pctF(m.max_drawdown, 0)}</td><td>{pctF(c.max_drawdown, 0)}</td></tr>
                {m.ter != null && (
                  <tr><td>Expense ratio (Direct)</td><td>{m.ter.toFixed(2)}%</td><td>{c.ter != null ? `${c.ter.toFixed(2)}%` : "—"}</td></tr>
                )}
              </tbody>
            </table>
          )}
          {r.metrics && (
            <div className="holdingFacts">
              {m.aum_cr != null && <span>Fund size ₹{Math.round(m.aum_cr).toLocaleString("en-IN")} cr</span>}
              {r.benchmark && m.beat_rate != null && (
                <span>Beat the {r.benchmark} in {pctF(m.beat_rate, 0)} of 3-yr periods
                  {m.down_capture != null && `, took ${pctF(m.down_capture, 0)} of its falls`}</span>
              )}
              {m.stocks > 0 && <span>{m.stocks} stocks{m.top10_pct != null && `, top 10 = ${Math.round(m.top10_pct)}%`}</span>}
              {m.managers?.length > 0 && (
                <span>Managed by {m.managers.join(", ")}{m.manager_changed && ` (new since ${fmtDate(m.manager_since)})`}</span>
              )}
            </div>
          )}
          {r.size_note && <div className="holding__note"><TriangleAlert size={14} className="ico" /> {r.size_note}</div>}
          {h.plan === "Regular" && (
            <div className="holding__note">
              <Banknote size={14} className="ico" /> Regular plan.{h.cost_gap != null && ` Its Direct plan returned about ${pctF(h.cost_gap)} more over the last year.`}{" "}
              Start new SIPs in the Direct plan of the same fund.
            </div>
          )}
          {h.alternatives.length > 0 && (
            <div className="alts">
              <div className="alts__title">Better-ranked {h.category} funds from other fund houses</div>
              {h.alternatives.map((a) => (
                <div key={a.code} className="alt">
                  <div className="alt__name">
                    #{a.rank} <Link to={`/fund/${a.code}`}>{a.name}</Link>
                  </div>
                  <div className="alt__meta">3 yr {pctF(a.cagr_3y)} · 5 yr {pctF(a.cagr_5y)} · worst fall {pctF(a.max_drawdown, 0)}</div>
                </div>
              ))}
            </div>
          )}
          <div className="holding__foot">
            <span className="mutedText">
              {h.units} units · NAV {h.nav ? `₹${h.nav.toFixed(2)}` : "—"} on {fmtDate(h.nav_date)}
              {h.code && <> · <Link to={`/fund/${h.code}`}>Fund page</Link></>}
              {h.info_url && <> · <a href={h.info_url} target="_blank" rel="noopener noreferrer">Factsheet ↗</a></>}
            </span>
            {h.source === "manual" && <button className="btnDanger" onClick={() => onRemove(h.ids[0])}>Remove</button>}
          </div>
        </div>
      )}
    </div>
  );
}

function GuestNote() {
  const { accountsEnabled } = useAuth();
  return (
    <div className="mutedText guestNote">
      You&apos;re not logged in, so this review is kept only in this browser tab and is gone when you close it.
      {accountsEnabled && <> <Link to="/login?next=%2Freview">Log in</Link> to save it and get alerts when a fund&apos;s rating changes.</>}
    </div>
  );
}

// The investor is back from approving an Account Aggregator consent: ask until the data is in. One request per
// consent even if the screen mounts twice (React's strict mode), since the holdings are handed over only once.
let aaInFlight = null;
function waitForAa({ id, key }) {
  if (aaInFlight?.id === id) return aaInFlight.promise;
  const promise = (async () => {
    const until = Date.now() + AA_WAIT_MS;
    while (Date.now() < until) {
      const r = await aaStatus(id, key);
      if (r.status === "done" && (r.review || r.holdings)) return r;
      if (r.status === "failed") throw new Error(r.message);
      if (r.status === "done") throw new Error("These holdings were already fetched. Please start again.");
      await new Promise((ok) => setTimeout(ok, AA_POLL_MS));
    }
    throw new Error("Your fund registrars are taking longer than usual. Please try again in a few minutes, or upload "
      + "your statement instead.");
  })();
  aaInFlight = { id, promise };
  return promise;
}

export default function ReviewScreen() {
  const navigate = useNavigate();
  const { user, panEnabled } = useAuth();
  // undefined until we know whether someone is logged in.
  const source = useMemo(() => (user === undefined ? undefined : user ? accountSource : guestSource), [user]);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  // Back from the Account Aggregator with a fetch still to collect.
  const [fetchingAa, setFetchingAa] = useState(() => !!loadSession(AA_PENDING_KEY, null));

  useEffect(() => {
    if (!source) return;
    let live = true;
    const pending = loadSession(AA_PENDING_KEY, null);
    if (!pending) {
      source.load().then((d) => live && setData(d)).catch((e) => live && setError(e.message));
      return () => { live = false; };
    }
    waitForAa(pending)
      .then((r) => source.fetchDone(r))
      .then((d) => { if (live) setData(d); })
      .catch(async (e) => {
        if (!live) return;
        setError(e.message);
        // Still show whatever was there before.
        try { const d = await source.load(); if (live) setData(d); } catch { /* the error above is enough */ }
      })
      .finally(() => {
        saveSession(AA_PENDING_KEY, undefined);
        if (live) { setFetchingAa(false); navigate("/review", { replace: true }); }
      });
    return () => { live = false; };
  }, [source, navigate]);

  const replace = (d) => { setData(d); setImporting(false); window.scrollTo(0, 0); };
  const onRemove = async (id) => {
    try { setData(await source.remove(id)); } catch (e) { setError(e.message); }
  };
  const onDeleteAll = async () => {
    const question = source.guest ? "Clear this review from your browser?"
      : "Delete your imported portfolio? Your account and saved plans stay.";
    if (!window.confirm(question)) return;
    try { setData(await source.clear()); } catch (e) { setError(e.message); }
  };

  return (
    <div className="page">
      <AppBar title="Portfolio review" onBack={() => navigate("/")} />
      <div className="body">
        {error && <div className="errorText" style={{ marginBottom: 16 }}>{error}</div>}
        {!data && !error && (
          <div className="pageLoading">
            {fetchingAa ? "Fetching your funds from your fund registrars… This usually takes under a minute."
              : "Loading your portfolio… (the server can take up to a minute to wake up)"}
          </div>
        )}

        {data?.empty && (
          <>
            <div className="stepTitle">Review your mutual funds</div>
            <div className="stepSubtitle">
              See how each fund ranks in its category, what you've really earned, where you're paying too much, and
              what to fix. Re-checked against fresh data every night.
            </div>
            {source.guest && <GuestNote />}
            <ImportPanel source={source} onDone={replace} />
          </>
        )}

        {data && !data.empty && (
          <>
            {data.parse_warnings?.length > 0 && (
              <div className="warningBox">
                <div className="warningBox__title">Some lines in the statement didn't add up</div>
                <div className="warningBox__item">Figures for those funds may be slightly off.</div>
              </div>
            )}
            {data.fetch_warnings?.length > 0 && (
              <div className="warningBox">
                <div className="warningBox__title">Some of your funds didn't come through fully</div>
                {data.fetch_warnings.map((w) => <div key={w} className="warningBox__item">{w}</div>)}
              </div>
            )}
            {source.guest && <GuestNote />}
            <Summary data={data} />
            <Insights insights={data.insights} />
            <Health health={data.health} />
            <Allocation allocation={data.allocation} target={data.target} />
            <LookThrough stocks={data.top_stocks} overlaps={data.overlaps} />
            <Tax tax={data.tax} />

            <div className="sectionHeading">Your funds</div>
            {data.holdings.map((h) => <HoldingCard key={h.code} h={h} onRemove={onRemove} />)}
            {data.unrecognised?.length > 0 && (
              <div className="mutedText" style={{ margin: "8px 0 16px" }}>
                Not recognised (closed or merged schemes): {data.unrecognised.map((u) => u.name).join(", ")}.
              </div>
            )}

            <div className="dataNote">
              Values use the latest NAVs. Ratings use fund rankings as of {fmtDate(data.rankings_date)}.
              {data.statement?.to && ` Statement period ${data.statement.from || "—"} to ${data.statement.to}.`}
            </div>

            {importing ? <ImportPanel source={source} onDone={replace} onCancel={() => setImporting(false)} /> : (
              <div className="resultsActions">
                <button className="btnOutline" onClick={() => setImporting(true)}>{panEnabled ? <><RefreshCw size={17} /> Fetch again, upload a statement or add a fund</> : <><FileText size={17} /> Upload a newer statement or add a fund</>}</button>
                <button className="btnDanger" onClick={onDeleteAll}>
                  {source.guest ? "Clear this review" : "Delete my imported portfolio"}
                </button>
              </div>
            )}
            <Disclaimer />
          </>
        )}
      </div>
    </div>
  );
}
