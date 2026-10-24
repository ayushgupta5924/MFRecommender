# MF Advisor

Goal-based mutual fund SIP plans and portfolio reviews for Indian investors.

- **Plan:** a 6-step questionnaire (about you, goal, finances, risk attitude, amount, review) gives an asset
  allocation, specific Direct-Growth funds ranked from daily data on every fund in India, the evidence behind
  each pick, and a projection range. No account needed; logged-in users can save plans.
- **Portfolio review** (login required): upload a CAMS / KFintech CAS PDF or add funds by hand. Every fund is
  rated In form / On track / Off track / Out of form against its category, with returns (XIRR), tax lots,
  Regular-plan cost, duplicate funds, asset mix against the saved plan and suggested alternatives.
- **Accounts:** sign-up and login by emailed one-time code only (no passwords).

- **Frontend:** React + Vite, deployed on Vercel
- **Backend:** FastAPI, deployed on Render
- **Data:** [AMFI NAVAll](https://www.amfiindia.com/spages/NAVAll.txt) (fund universe and SEBI categories) and
  [mfapi.in](https://www.mfapi.in) (NAV history), re-ranked nightly by a GitHub Action

## How it works

```
GitHub Action (nightly, 00:30 IST)
  └─ backend/scripts/build_rankings.py
       ├─ AMFI NAVAll → open-ended Direct-Growth funds, mapped to 17 buckets
       ├─ mfapi.in    → NAV history for each fund (~550 funds)
       ├─ metrics     → 1/3/5/10-yr CAGR, rolling returns, volatility, max drawdown, Sortino
       ├─ scores      → percentile within bucket, weighted per profile (conservative / balanced / aggressive)
       ├─ scheme map  → every open-ended scheme (any plan/option) → its Direct-Growth twin and category
       └─ commits backend/app/data/rankings.json and scheme_map.json

API request  POST /api/portfolio
  ├─ allocation.py         equity / hybrid / debt mix from risk score, horizon, life stage, goal
  ├─ consolidate           fund count by budget, every SIP ≥ ₹500, merges never add risk
  ├─ fund selection        best-scored fund per bucket, prefers 5+ yr records, spreads across AMCs
  └─ projections           category rolling returns, pessimistic / expected / optimistic

API request  GET /api/review   (services/review.py)
  ├─ scheme map            Regular / IDCW holdings rated through their Direct-Growth twin
  ├─ mfapi.in              latest NAVs, and Direct vs Regular 1-yr return gap
  ├─ rating                position in the category's nightly ranking, by quarter
  └─ checks                out-of-form funds, Regular plans, duplicates, too many funds, sector share,
                           drift from saved plan, IDCW, unrated funds, LTCG / STCG / ELSS lock-in
```

Key rules (`backend/app/services/allocation.py`):

| Rule | Limit |
|---|---|
| Horizon under 3 years, or emergency corpus | No equity or hybrid |
| Horizon under 4 / 5 / 7 years | Equity ≤ 25% / 35% / 60% |
| Near retirement / retired | Equity ≤ 50% / 40% |
| Home purchase within 5 years | Equity ≤ 30% |
| Tax saving (old regime) | ELSS up to ₹12,500/month (80C limit) |

## Local development

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
# Local settings: SQLite file, login codes printed to this terminal, cookies over http
EMAIL_DEV_MODE=1 COOKIE_SECURE=0 uvicorn main:app --reload --port 8000
python -m pytest -q tests

# Frontend (from the repo root)
npm install
npm run dev          # http://localhost:5173, forwards /api to http://localhost:8000
npm run lint && npm run build
```

Rebuild rankings locally (takes about 2 minutes; `--cache-dir` reuses downloads between runs):

```bash
cd backend
python -m scripts.build_rankings --cache-dir ../.cache/mf
```

## Deployment

### Vercel (frontend)
- `vercel.json` forwards `/api/*` to the Render backend, so the browser only ever talks to the Vercel domain and the
  login cookie is first-party in every browser. If the backend URL changes, update it there.
  (`VITE_API_URL` is no longer used.)
- All other paths serve `index.html`, so every screen has its own URL and survives a refresh.
- `vercel.json` skips builds when nothing outside `backend/` or `.github/` changed since the last deployment (e.g. the nightly data commit).

### Render (backend)
- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment variables:
  - `PYTHON_VERSION=3.11.9`
  - `RANKINGS_URL=https://raw.githubusercontent.com/<owner>/<repo>/main/backend/app/data/rankings.json`
    (the API pulls the nightly file every 6 hours without a redeploy)
  - `ALLOWED_ORIGINS=https://<your-vercel-domain>` (comma-separated; defaults to `*`)
  - `DATABASE_URL` — the Neon connection string for the **production** branch (pooled or direct both work).
    **Required for accounts**: until it's set, login, review and saving stay hidden, because a SQLite file on
    Render would be wiped on every deploy.
  - `AUTH_SECRET` — a long random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`).
    Changing it logs everyone out.
  - `RESEND_API_KEY` and `EMAIL_FROM` (e.g. `MF Advisor <no-reply@yourdomain.in>`, on a domain verified in Resend)
    for login codes. Without them sign-up and login reply "not available yet".
  - `ALERTS_TOKEN` — a long random string; must match the `ALERTS_TOKEN` GitHub Actions secret used by
    `portfolio-alerts.yml` (weekly). Without it portfolio alert emails don't run.
  - `SITE_URL` (optional) — public site address used in email links; defaults to the Vercel URL.
  - `BRAND_NAME` (optional) — name used in login emails; defaults to "MF Advisor".

The nightly data commit contains `[skip render]`, so it doesn't trigger a Render redeploy.

### GitHub Actions
- `refresh-rankings.yml`: nightly rankings rebuild. Needs **Settings → Actions → General → Workflow permissions →
  Read and write**. Can also be run manually from the Actions tab.
- `ci.yml`: backend tests, frontend lint and build on every push and PR.

### Database (Neon Postgres)
- Schema changes are Alembic migrations in `backend/migrations/versions`, applied automatically when the API
  starts. After changing `backend/app/db/tables.py`, run `alembic revision --autogenerate -m "..."` in `backend/`,
  read the generated file, and commit it. A test fails if the tables and migrations ever disagree.
- Use the `production` branch only for the live site. For local testing against Postgres, create a separate Neon
  branch (e.g. `dev`) and use its connection string, so tests never touch real accounts.
- CI runs the backend tests on both SQLite and Postgres 16. Locally:
  `TEST_DATABASE_URL=postgresql://... python -m pytest -q tests` (use an empty, throwaway database).
- Expired login codes and sessions are cleared on every startup.

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/portfolio` | Full plan: funds, allocation, projections, warnings |
| POST | `/api/recommend` | Fund list only (legacy) |
| GET | `/api/health` | Status and data date |
| GET | `/api/categories` | Category medians per bucket |
| POST | `/api/auth/signup/start`, `/api/auth/login/start` | Email a 6-digit code |
| POST | `/api/auth/verify` | Check the code, start a 30-day session (HttpOnly cookie) |
| GET / POST | `/api/auth/me`, `/api/auth/logout` | Current user, log out |
| DELETE | `/api/account` | Delete the account and all its data |
| GET / DELETE | `/api/review` | Review of the saved portfolio, or delete it |
| POST | `/api/review/upload` | CAS PDF + password → holdings → review |
| POST / DELETE | `/api/review/holdings[/{id}]` | Add a fund by hand, remove one |
| GET | `/api/funds/search?q=` | Any open-ended scheme by name |
| GET / POST / DELETE | `/api/plans[/{id}]` | Saved plans |

Example request:

```json
{
  "life_stage": "peak_earning",
  "goal": "wealth_creation",
  "risk_tolerance": "moderate",
  "risk_score": 62,
  "monthly_budget": 25000,
  "horizon_years": 12,
  "target_amount": 10000000
}
```

## Before launch

- **Compliance details** in `src/constants/compliance.js` are placeholders (registration number, BASL ID, CIN,
  officers, grievance email, address). Replace them with your real details.
- Review the disclaimer (`src/components/Disclaimer.jsx`) and footer (`src/components/Footer.jsx`) with your
  compliance officer.
- **Every month, by the 7th:** update `src/constants/complaints.js` (SEBI's Annexure B format) and deploy.
- Disclosure pages: `/investor-charter` (SEBI's text), `/complaints`, `/how-advice-works` (use of automated tools and
  AI, regulation 18), `/privacy` (DPDP notice). Have the last two reviewed. If the privacy notice changes
  materially, bump `PRIVACY_VERSION` in both `src/constants/privacy.js` and `backend/app/services/auth.py`.
- Consent is required at sign-up and before holdings are stored, and recorded with the notice version.
  Portfolio alerts are opt-in.
- Fund cards point to the fund house or MF Central rather than a distributor, to keep advice and distribution
  separate.

## Privacy

From a CAS we keep only fund-level data (scheme, units, cost, transactions). The investor's name, PAN, email,
phone and address on the statement, and the PDF itself, are never stored. Login codes and session tokens are
stored only as HMACs. Users can delete their portfolio or their whole account from the app.

Every plan and portfolio review shown is kept in `advice_records` (inputs, risk profile and the advice itself)
for `ADVICE_RETENTION_YEARS` (default 5), as SEBI requires advisers to keep records of advice, including for
prospective clients before onboarding. Visitors' plans are stored without identity; clients' records carry their
name and email and are kept even after the account is deleted, then purged automatically. The Investor Charter
(SEBI circular 2025/80) is at `/investor-charter` and is emailed at sign-up.

## Limitations

- Rankings use past NAV performance only. Expense ratio, AUM, portfolio holdings and fund manager changes are not
  in the free data sources and are not considered.
- Projections are estimates from category-level historical returns, not guarantees.
- mfapi.in is a free community API; if it is down, the nightly job fails safely and keeps the previous rankings.
- Review ratings cover the categories the planner ranks. Sector/theme, international, gold and some debt categories
  are shown but not rated. Overlap is judged by category, not stock-level holdings (not in free data).
