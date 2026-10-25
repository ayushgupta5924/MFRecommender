// Privacy notice, written to the Digital Personal Data Protection Act, 2023 and DPDP Rules, 2025:
// itemised, in plain language, with purposes, retention, rights and a contact.
// When this changes materially, bump PRIVACY_VERSION here AND in backend/app/services/auth.py, so
// consents record which version people agreed to. Have it reviewed by your legal / compliance adviser.

export const PRIVACY_VERSION = "2026-10-25.2";

export const PRIVACY = [
  {
    title: "What we collect and why",
    items: [
      { what: "Questionnaire answers", detail: "Age, life stage, goal, income, expenses, loan EMIs, dependents, savings, insurance and your answers on risk.", why: "To assess your risk profile and suitability and build your plan, as SEBI requires before giving advice." },
      { what: "Account details", detail: "Your full name and email address.", why: "To create your account, log you in with one-time codes, and send emails you ask for." },
      { what: "Your fund holdings", detail: "From a statement you upload, funds you fetch from MF Central with your PAN, or funds you add: scheme names, units, amounts invested and transactions. We do not keep your PAN, name, address, phone number, email, bank details, folio numbers or the statement PDF. If you review without an account, your holdings are not stored on our servers: they stay in your browser tab until you close it, and only the record of advice below is kept.", why: "To review your portfolio and, if you have an account and switch it on, alert you when a fund's rating changes." },
      { what: "Records of advice", detail: "Your answers and the plans and reviews we showed you.", why: "SEBI requires investment advisers to keep records of advice, including for people who have not yet become clients." },
      { what: "Technical data", detail: "A login cookie (only after you log in), your questionnaire answers kept in your own browser so a page refresh doesn't lose them, and a review done without an account, kept in your browser tab until you close it, and your colour theme. Anonymous page-visit counts (which page, the referring site, country, device type) through Vercel Web Analytics, which sets no cookies and doesn't identify you.", why: "To keep you logged in and the site working, and to see which pages people use so we can improve them. We do not use advertising or tracking cookies." },
    ],
  },
  {
    title: "How long we keep it",
    points: [
      "Account details, saved plans and imported holdings: until you delete them or your account.",
      "Holdings reviewed without an account: not stored, apart from the record of advice.",
      "Records of advice: 5 years from when the advice was given, then deleted automatically. These are kept even if you delete your account, because SEBI requires it.",
      "Login codes: deleted within a day. Login sessions: 30 days.",
      "Answers saved in your browser: until you clear them (\"Clear my answers\"), log out, or clear your browser's site data. A review done without an account: until you close the tab or clear it.",
    ],
  },
  {
    title: "Who we share it with",
    points: [
      "We do not sell your data or share it for marketing.",
      "Service providers who process it on our behalf: Vercel (website hosting and anonymous visit counts), Render (application server), Neon (database), Resend (sending emails). They may store data outside India.",
      "If you fetch your funds with your PAN: we send your PAN and the mobile number or email you enter to smallcase Technologies (our technology partner) and MF Central (run by CAMS and KFintech, the registrars of all mutual funds), only to find your funds and send you a one-time password. They return your holdings to us, and we keep only the fund-level data described above.",
      "We look up fund prices from AMFI and mfapi.in using only fund codes, never your personal details.",
      "Regulators or authorities, such as SEBI, when the law requires it.",
    ],
  },
  {
    title: "Your rights",
    points: [
      "Access: see your saved plans and portfolio in your account.",
      "Correction: update your answers or holdings at any time.",
      "Erasure: delete your portfolio, saved plans or whole account from your account page (records of advice are kept for the period SEBI requires).",
      "Withdraw consent: delete your data as above, and switch off alert emails from your account or any alert.",
      "Grievances: contact us using the details below. If you are not satisfied, you may approach the Data Protection Board of India.",
      "Nominate someone to exercise these rights for you in case of death or incapacity, by writing to us.",
    ],
  },
  {
    title: "Security",
    points: [
      "All connections use HTTPS. Login codes and session tokens are stored only in scrambled (hashed) form.",
      "There are no passwords to leak: login is by one-time codes sent to your email.",
      "If a breach affects your data, we will inform you and the Data Protection Board as the law requires.",
    ],
  },
  {
    title: "Age",
    points: ["This service is for adults. Please do not use it if you are under 18."],
  },
];
