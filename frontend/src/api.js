const API_BASE = process.env.REACT_APP_API_BASE_URL || "http://localhost:5000/api";

async function get(path, params = {}) {
  const url = new URL(`${API_BASE}${path}`);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

async function post(path, body = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.error || `API error ${res.status}`);
  }
  return res.json();
}

export const api = {
  states: (lang) => get("/states", { lang }),
  districts: (lang, stateId) => get("/districts", { lang, state_id: stateId }),
  crops: (lang) => get("/crops", { lang }),
  prices: (lang, { stateId, districtId, cropId, date, page, perPage } = {}) =>
    get("/prices", {
      lang,
      state_id: stateId,
      district_id: districtId,
      crop_id: cropId,
      date,
      page,
      per_page: perPage,
    }),
  trend: (cropId, marketId, days = 7) => get("/prices/trend", { crop_id: cropId, market_id: marketId, days }),
  anomalies: (lang, { stateId, districtId, date, deviationPct } = {}) =>
    get("/prices/anomalies", {
      lang,
      state_id: stateId,
      district_id: districtId,
      date,
      deviation_pct: deviationPct,
    }),
  forecast: (cropId, marketId, { daysAhead, historyDays } = {}) =>
    get("/prices/forecast", {
      crop_id: cropId,
      market_id: marketId,
      days_ahead: daysAhead,
      history_days: historyDays,
    }),
  ask: (question, lang) => post("/ask", { question, lang }),
};
