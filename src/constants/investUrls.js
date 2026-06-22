const AFFILIATE_CODE = "YOUR_GROWW_AFFILIATE_CODE";
const BASE = "https://groww.in/mutual-funds";

export const INVEST_URLS = {
  "120503": `${BASE}/axis-large-cap-fund-direct-growth?ref=${AFFILIATE_CODE}`,
  "118989": `${BASE}/hdfc-medium-term-opportunities-fund-direct-growth?ref=${AFFILIATE_CODE}`,
  "118590": `${BASE}/hdfc-balanced-advantage-fund-direct-growth?ref=${AFFILIATE_CODE}`,
  "120505": `${BASE}/hdfc-liquid-direct-plan-growth?ref=${AFFILIATE_CODE}`,
  "119551": `${BASE}/axis-midcap-fund-direct-growth?ref=${AFFILIATE_CODE}`,
};

export const FALLBACK_URL = `https://groww.in/mutual-funds?ref=${AFFILIATE_CODE}`;