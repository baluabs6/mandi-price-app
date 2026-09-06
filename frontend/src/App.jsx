import React, { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { api } from "./api";
import LanguageSwitcher from "./components/LanguageSwitcher";
import FilterBar from "./components/FilterBar";
import PriceTable from "./components/PriceTable";
import AskAssistant from "./components/AskAssistant";
import "./styles.css";

const PER_PAGE = 50;

export default function App() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;

  const [states, setStates] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [crops, setCrops] = useState([]);

  const [stateId, setStateId] = useState(null);
  const [districtId, setDistrictId] = useState(null);
  const [cropId, setCropId] = useState(null);

  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [anomalyIds, setAnomalyIds] = useState(new Set());

  // load reference lists whenever language changes
  useEffect(() => {
    api.states(lang).then(setStates).catch(() => {});
    api.crops(lang).then(setCrops).catch(() => {});
  }, [lang]);

  // load districts when state changes
  useEffect(() => {
    api
      .districts(lang, stateId)
      .then(setDistricts)
      .catch(() => {});
    setDistrictId(null);
  }, [lang, stateId]);

  const loadPrices = useCallback(
    (targetPage, append) => {
      const setBusy = append ? setLoadingMore : setLoading;
      setBusy(true);
      setError(null);
      api
        .prices(lang, { stateId, districtId, cropId, page: targetPage, perPage: PER_PAGE })
        .then((data) => {
          setRows((prev) => (append ? [...prev, ...data.results] : data.results));
          setTotal(data.total);
          setPage(data.page);
        })
        .catch(() => setError("Could not load prices right now."))
        .finally(() => setBusy(false));
    },
    [lang, stateId, districtId, cropId]
  );

  // reset to page 1 whenever filters/language change
  useEffect(() => {
    loadPrices(1, false);
  }, [loadPrices]);

  // fetch anomalies for the current filter scope, independent of pagination
  useEffect(() => {
    api
      .anomalies(lang, { stateId, districtId })
      .then((data) => setAnomalyIds(new Set(data.anomalies.map((a) => a.id))))
      .catch(() => setAnomalyIds(new Set()));
  }, [lang, stateId, districtId]);

  const hasMore = rows.length < total;

  return (
    <div className="app-container">
      <header className="app-header">
        <div>
          <h1>{t("title")}</h1>
          <p className="subtitle">{t("subtitle")}</p>
        </div>
        <LanguageSwitcher />
      </header>

      <FilterBar
        states={states}
        districts={districts}
        crops={crops}
        stateId={stateId}
        districtId={districtId}
        cropId={cropId}
        onStateChange={setStateId}
        onDistrictChange={setDistrictId}
        onCropChange={setCropId}
      />

      <AskAssistant />

      {error && <p className="error-msg">{error}</p>}
      <PriceTable rows={rows} loading={loading} anomalyIds={anomalyIds} />

      {!loading && rows.length > 0 && (
        <div className="pagination-bar">
          <p className="pagination-status">
            {t("showing_of", { shown: rows.length, total })}
          </p>
          {hasMore && (
            <button
              className="load-more-btn"
              onClick={() => loadPrices(page + 1, true)}
              disabled={loadingMore}
            >
              {loadingMore ? t("loading") : t("load_more")}
            </button>
          )}
        </div>
      )}

      <footer className="app-footer">
        <p>{t("source_note")}</p>
      </footer>
    </div>
  );
}
