# MF Advisor

Goal-based mutual fund SIP plans for Indian investors. The investor answers four steps (life stage, goal,
a 6-question risk profile, amount and horizon) and gets an asset allocation, specific Direct-Growth funds
ranked from daily data on every fund in India, the evidence behind each pick, and a projection range.

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
       └─ commits backend/app/data/rankings.json

API request  POST /api/portfolio
  ├─ allocation.py         equity / hybrid / debt mix from risk score, horizon, life stage, goal
  ├─ consolidate           fund count by budget, every SIP ≥ ₹500, merges never add risk
  ├─ fund selection        best-scored fund per bucket, prefers 5+ yr records, spreads across AMCs
  └─ projections           category rolling returns, pessimistic / expected / optimistic
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
uvicorn main:app --reload --port 8000
python -m pytest -q tests

# Frontend (from the repo root)
npm install
npm run dev          # http://localhost:5173, talks to http://localhost:8000 by default
npm run lint && npm run build
```

Rebuild rankings locally (takes about 2 minutes; `--cache-dir` reuses downloads between runs):

```bash
cd backend
python -m scripts.build_rankings --cache-dir ../.cache/mf
```

## Deployment

### Vercel (frontend)
- Environment variable: `VITE_API_URL=https://<your-render-service>.onrender.com`
- `vercel.json` skips builds when a commit only touches `backend/` or `.github/` (e.g. the nightly data commit).

### Render (backend)
- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment variables:
  - `PYTHON_VERSION=3.11.9`
  - `RANKINGS_URL=https://raw.githubusercontent.com/<owner>/<repo>/main/backend/app/data/rankings.json`
    (the API pulls the nightly file every 6 hours without a redeploy)
  - `ALLOWED_ORIGINS=https://<your-vercel-domain>` (comma-separated; defaults to `*`)

The nightly data commit contains `[skip render]`, so it doesn't trigger a Render redeploy.

### GitHub Actions
- `refresh-rankings.yml`: nightly rankings rebuild. Needs **Settings → Actions → General → Workflow permissions →
  Read and write**. Can also be run manually from the Actions tab.
- `ci.yml`: backend tests, frontend lint and build on every push and PR.

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/portfolio` | Full plan: funds, allocation, projections, warnings |
| POST | `/api/recommend` | Fund list only (legacy) |
| GET | `/api/health` | Status and data date |
| GET | `/api/categories` | Category medians per bucket |

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

## Limitations

- Rankings use past NAV performance only. Expense ratio, AUM, portfolio holdings and fund manager changes are not
  in the free data sources and are not considered.
- Projections are estimates from category-level historical returns, not guarantees.
- mfapi.in is a free community API; if it is down, the nightly job fails safely and keeps the previous rankings.
