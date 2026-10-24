import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { deleteAccount, deletePlan, getPlan, listPlans } from "../api";
import { useAuth } from "../auth";
import "../styles/AccountScreen.css";
import "../styles/ResultsScreen.css";
import "../styles/shared.css";
import { fmt, fmtDate } from "../utils/format";
import { LAST_PLAN_KEY, save } from "../utils/storage";
import AppBar from "./AppBar";

const GOAL_LABEL = {
  financial_freedom: "Financial freedom", buy_home: "Buy a home", child_education: "Child's education",
  retirement: "Retirement", tax_saving: "Tax saving", emergency_corpus: "Emergency fund", wealth_creation: "Wealth creation",
};

export default function AccountScreen() {
  const navigate = useNavigate();
  const { user, setUser, logout } = useAuth();
  const [plans, setPlans] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listPlans().then(setPlans).catch((e) => setError(e.message));
  }, []);

  const open = async (id) => {
    try {
      const p = await getPlan(id);
      save(LAST_PLAN_KEY, { payload: p.profile, results: p.result, savedId: p.id });
      navigate("/plan/results");
    } catch (e) {
      setError(e.message);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this saved plan?")) return;
    try {
      await deletePlan(id);
      setPlans((ps) => ps.filter((p) => p.id !== id));
    } catch (e) {
      setError(e.message);
    }
  };

  const onLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  const onDelete = async () => {
    if (!window.confirm("Permanently delete your account, saved plans and imported portfolio? This can't be undone.")) return;
    try {
      await deleteAccount();
      setUser(null);
      navigate("/", { replace: true });
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="page">
      <AppBar title="Your account" onBack={() => navigate("/")} />
      <div className="body">
        <div className="card accountCard">
          <div className="accountCard__name">{user.full_name}</div>
          <div className="mutedText">{user.email}</div>
          <button className="linkBtn" style={{ marginTop: 12 }} onClick={onLogout}>Log out</button>
        </div>

        <Link className="card accountLink" to="/review">
          <span>📊 Portfolio review</span><span className="accountLink__arrow">→</span>
        </Link>

        <div className="sectionHeading">Saved plans</div>
        {error && <div className="errorText">{error}</div>}
        {plans === null && !error && <div className="mutedText">Loading…</div>}
        {plans?.length === 0 && (
          <div className="card mutedText">
            No saved plans yet. <Link to="/plan">Build a plan</Link> and tap "Save to my account" on the results.
          </div>
        )}
        {plans?.map((p) => (
          <div key={p.id} className="card planRow">
            <button className="planRow__main" onClick={() => open(p.id)}>
              <div className="planRow__name">{p.name}</div>
              <div className="mutedText">
                {GOAL_LABEL[p.goal] || p.goal} · {fmt(p.monthly_investment)}/month · {p.horizon_years} yrs
                {p.risk_label && ` · ${p.risk_label}`}
              </div>
              <div className="mutedText">Saved {fmtDate(p.created_at.slice(0, 10))}</div>
            </button>
            <button className="btnDanger" onClick={() => remove(p.id)} aria-label={`Delete ${p.name}`}>Delete</button>
          </div>
        ))}

        <div className="dangerZone">
          <div className="mutedText">Deleting your account removes your saved plans and imported portfolio for good.</div>
          <button className="btnDanger" onClick={onDelete}>Delete my account</button>
        </div>
      </div>
    </div>
  );
}
