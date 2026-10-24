import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { startLogin, startSignup, verifyCode } from "../api";
import { ComingSoon, useAuth } from "../auth";
import "../styles/AuthScreen.css";
import "../styles/shared.css";
import { usePersistentState } from "../utils/storage";
import AppBar from "./AppBar";

// Only same-site paths, so a crafted link can't bounce someone to another site after login.
function safeNext(next) {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export default function AuthScreen({ mode }) {
  const isSignup = mode === "signup";
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const { user, setUser, accountsEnabled } = useAuth();

  // Kept across a refresh so someone waiting for the email doesn't have to start over.
  const [pending, setPending] = usePersistentState("mfa:auth", null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState(params.get("email") || "");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [now, setNow] = useState(() => Date.now());
  const codeRef = useRef(null);

  const onCodeStep = pending && pending.mode === mode;
  const waitSeconds = onCodeStep ? Math.max(0, Math.ceil((pending.resendAt - now) / 1000)) : 0;

  useEffect(() => {
    if (!onCodeStep) return undefined;
    codeRef.current?.focus();
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [onCodeStep]);

  if (user) return <Navigate to={next} replace />;
  if (accountsEnabled === false) return <ComingSoon />;

  const send = async (e) => {
    e?.preventDefault();
    setError(null); setBusy(true);
    try {
      const target = onCodeStep ? pending.email : email;
      const res = isSignup ? await startSignup(onCodeStep ? pending.name : name, target) : await startLogin(target);
      setPending({ mode, email: res.email, name: onCodeStep ? pending.name : name,
                   resendAt: Date.now() + res.resend_after_seconds * 1000 });
      setNow(Date.now());
      setCode("");
    } catch (err) {
      setError({ message: err.message, status: err.status });
    } finally {
      setBusy(false);
    }
  };

  const verify = async (value) => {
    setError(null); setBusy(true);
    try {
      const u = await verifyCode(pending.email, value, mode);
      setPending(null);
      setUser(u);
      navigate(next, { replace: true });
    } catch (err) {
      setError({ message: err.message, status: err.status });
      setCode("");
    } finally {
      setBusy(false);
    }
  };

  const onCodeChange = (v) => {
    const digits = v.replace(/\D/g, "").slice(0, 6);
    setCode(digits);
    if (digits.length === 6 && !busy) verify(digits);
  };

  const otherLink = isSignup ? "/login" : "/signup";
  const carry = (extra = {}) => {
    const q = new URLSearchParams({ ...(next !== "/" ? { next } : {}), ...extra });
    return `${otherLink}${q.toString() ? `?${q}` : ""}`;
  };

  return (
    <div className="page">
      <AppBar title={isSignup ? "Create account" : "Log in"} onBack={() => navigate(-1)} />
      <div className="body authBody">
        <div className="card authCard">
          {!onCodeStep ? (
            <form onSubmit={send}>
              <div className="authCard__title">{isSignup ? "Create your account" : "Welcome back"}</div>
              <div className="authCard__sub">
                {isSignup
                  ? "Save your plans and get your portfolio reviewed. We'll email you a code to confirm it's you."
                  : "We'll email you a 6-digit code. No password needed."}
              </div>
              {isSignup && (
                <div className="fieldWrap">
                  <label className="fieldLabel" htmlFor="name">Full name</label>
                  <input id="name" className="fieldInput authInput" autoComplete="name" value={name}
                    onChange={(e) => setName(e.target.value)} placeholder="As on your PAN" required minLength={2} />
                </div>
              )}
              <div className="fieldWrap">
                <label className="fieldLabel" htmlFor="email">Email</label>
                <input id="email" type="email" className="fieldInput authInput" autoComplete="email" value={email}
                  onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required />
              </div>
              <button className="btnBlue" type="submit" disabled={busy || !email || (isSignup && name.trim().length < 2)}>
                {busy ? "Sending code…" : "Send code"}
              </button>
            </form>
          ) : (
            <div>
              <div className="authCard__title">Check your email</div>
              <div className="authCard__sub">
                We sent a 6-digit code to <b>{pending.email}</b>. It expires in 10 minutes.
              </div>
              <div className="fieldWrap">
                <label className="fieldLabel" htmlFor="code">Code</label>
                <input id="code" ref={codeRef} className="fieldInput authInput authCode" inputMode="numeric"
                  autoComplete="one-time-code" value={code} onChange={(e) => onCodeChange(e.target.value)}
                  placeholder="••••••" maxLength={6} disabled={busy} />
              </div>
              <button className="btnBlue" onClick={() => verify(code)} disabled={busy || code.length !== 6}>
                {busy ? "Checking…" : isSignup ? "Create account" : "Log in"}
              </button>
              <div className="authCard__row">
                <button type="button" className="linkBtn" onClick={() => { setPending(null); setError(null); setEmail(pending.email); }}>
                  Use a different email
                </button>
                <button type="button" className="linkBtn" onClick={send} disabled={busy || waitSeconds > 0}>
                  {waitSeconds > 0 ? `Resend in ${waitSeconds}s` : "Resend code"}
                </button>
              </div>
              <div className="mutedText authCard__note">Can't find it? Check your spam or promotions folder.</div>
            </div>
          )}

          {error && (
            <div className="errorText">
              {error.message}{" "}
              {error.status === 404 && !isSignup && <Link to={carry({ email })}>Create an account</Link>}
              {error.status === 409 && isSignup && <Link to={carry({ email })}>Log in</Link>}
            </div>
          )}
        </div>

        {!onCodeStep && (
          <div className="authSwitch">
            {isSignup ? "Already have an account? " : "New here? "}
            <Link to={carry()}>{isSignup ? "Log in" : "Create an account"}</Link>
          </div>
        )}
        <div className="mutedText authPrivacy">
          We use your email only to log you in and to send updates you ask for. You can delete your account and
          everything in it at any time.
        </div>
      </div>
    </div>
  );
}
