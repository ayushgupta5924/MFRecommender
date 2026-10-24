import { useNavigate } from "react-router-dom";
import { COMPLAINTS } from "../constants/complaints";
import { CHARTER_SOURCE } from "../constants/investorCharter";
import "../styles/InfoPage.css";
import "../styles/shared.css";
import AppBar from "./AppBar";

const sum = (rows, key) => rows.reduce((t, r) => t + (r[key] || 0), 0);

function TrendTable({ label, rows, keyName, unit }) {
  return (
    <div className="tableWrap">
      <table className="dataTable">
        <thead>
          <tr><th>Sr. No.</th><th>{label}</th><th>Carried forward from previous {unit}</th><th>Received</th><th>Resolved*</th><th>Pending#</th></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r[keyName]}><td>{i + 1}</td><td>{r[keyName]}</td><td>{r.carried}</td><td>{r.received}</td><td>{r.resolved}</td><td>{r.pending}</td></tr>
          ))}
          <tr className="dataTable__total">
            <td></td><td>Grand Total</td><td>{rows[0]?.carried ?? 0}</td><td>{sum(rows, "received")}</td>
            <td>{sum(rows, "resolved")}</td><td>{rows[rows.length - 1]?.pending ?? 0}</td>
          </tr>
        </tbody>
      </table>
      <div className="mutedText tableNote">
        * Inclusive of complaints of previous {unit}s resolved in the current {unit}.
        <br /># Inclusive of complaints pending as on the last day of the {unit}.
      </div>
    </div>
  );
}

export default function ComplaintsScreen() {
  const navigate = useNavigate();
  const c = COMPLAINTS;
  const total = (key) => sum(c.rows, key);
  return (
    <div className="page">
      <AppBar title="Complaints data" onBack={() => navigate(-1)} />
      <div className="body infoPage">
        <h1>Investor complaints data</h1>
        <p className="mutedText">
          Published monthly in the format prescribed by SEBI (circular {CHARTER_SOURCE.circular}, Annexure B).
        </p>

        <section className="card">
          <h2>Data for the month ending {c.monthEnding}</h2>
          <div className="tableWrap">
            <table className="dataTable">
              <thead>
                <tr>
                  <th>Sr. No.</th><th>Received from</th><th>Pending at the end of last month</th><th>Received</th>
                  <th>Resolved*</th><th>Total Pending#</th><th>Pending complaints &gt; 3 months</th>
                  <th>Average Resolution time^ (in days)</th>
                </tr>
              </thead>
              <tbody>
                {c.rows.map((r, i) => (
                  <tr key={r.source}>
                    <td>{i + 1}</td><td>{r.source}</td><td>{r.pendingStart}</td><td>{r.received}</td><td>{r.resolved}</td>
                    <td>{r.pending}</td><td>{r.over3Months}</td><td>{r.avgDays ?? "—"}</td>
                  </tr>
                ))}
                <tr className="dataTable__total">
                  <td></td><td>Grand Total</td><td>{total("pendingStart")}</td><td>{total("received")}</td>
                  <td>{total("resolved")}</td><td>{total("pending")}</td><td>{total("over3Months")}</td><td>—</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="tableNote">
            Number of complaints received during month against the IA due to impersonation by some other entity:{" "}
            <b>{c.impersonation}</b>
          </p>
          <div className="mutedText tableNote">
            * Inclusive of complaints of previous months resolved in the current month.
            <br /># Inclusive of complaints pending as on the last day of the month.
            <br />^ Average Resolution time is the sum total of time taken to resolve each complaint in days, in the
            current month divided by total number of complaints resolved in the current month.
          </div>
        </section>

        <section className="card">
          <h2>Trend of monthly disposal of complaints</h2>
          <TrendTable label="Month" rows={c.monthly} keyName="month" unit="month" />
        </section>

        <section className="card">
          <h2>Trend of annual disposal of complaints</h2>
          <TrendTable label="Year" rows={c.annual} keyName="year" unit="year" />
        </section>
      </div>
    </div>
  );
}
