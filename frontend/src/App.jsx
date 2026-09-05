import React, { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { api } from "./api";
import LanguageSwitcher from "./components/LanguageSwitcher";
import FilterBar from "./components/FilterBar";
import PriceTable from "./components/PriceTable";
import "./styles.css";

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  const loadPrices = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .prices(lang, { stateId, districtId, cropId })
      .then((data) => setRows(data.results))
      .catch(() => setError("Could not load prices right now."))
      .finally(() => setLoading(false));
  }, [lang, stateId, districtId, cropId]);

  useEffect(() => {
    loadPrices();
  }, [loadPrices]);

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

      {error && <p className="error-msg">{error}</p>}
      <PriceTable rows={rows} loading={loading} />

      <footer className="app-footer">
        <p>{t("source_note")}</p>
      </footer>
    </div>
  );
}
