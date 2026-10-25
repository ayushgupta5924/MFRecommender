import { useEffect } from "react";

const SITE = "MF Advisor";
const DEFAULT_DESCRIPTION = "Goal-based mutual fund SIP plans and honest portfolio reviews. Every Direct fund in India "
  + "ranked against its category every night.";

function setMeta(selector, attr, value) {
  const el = document.querySelector(selector);
  if (el) el.setAttribute(attr, value);
}

// Title and description for the current screen, also used by link previews that run scripts.
export function usePageMeta(title, description = DEFAULT_DESCRIPTION) {
  useEffect(() => {
    const full = title ? `${title} · ${SITE}` : `${SITE}: goal-based mutual fund plans and reviews`;
    document.title = full;
    setMeta('meta[name="description"]', "content", description);
    setMeta('meta[property="og:title"]', "content", full);
    setMeta('meta[property="og:description"]', "content", description);
    setMeta('link[rel="canonical"]', "href", `${window.location.origin}${window.location.pathname}`);
  }, [title, description]);
}
