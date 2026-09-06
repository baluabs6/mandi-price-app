import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import TrendChart from "./TrendChart";

const QUINTAL_TO_KG = 100;

function formatPrice(value, unit) {
  if (value === null || value === undefined) return "—";
  return unit === "kg" ? (value / QUINTAL_TO_KG).toFixed(2) : value;
}

export default function PriceTable({ rows, loading, anomalyIds }) {
  const { t } = useTranslation();
  const [unit, setUnit] = useState("quintal");

  if (loading) return <p className="status-msg">{t("loading")}</p>;
  if (!rows || rows.length === 0) return <p className="status-msg">{t("no_data")}</p>;

  return (
    <div>
      <div className="unit-toggle">
        <label>
          <input
            type="checkbox"
            checked={unit === "kg"}
            onChange={(e) => setUnit(e.target.checked ? "kg" : "quintal")}
          />
          {t("per_kg")} ({t("per_quintal")} ÷ 100)
        </label>
      </div>

      <div className="price-table-wrap">
        <table className="price-table">
          <thead>
            <tr>
              <th>{t("crop")}</th>
              <th>{t("market")}</th>
              <th>{t("district")}</th>
              <th>{t("min_price")}</th>
              <th>{t("max_price")}</th>
              <th>{t("modal_price")}</th>
              <th>{t("trend_7d")}</th>
              <th>{t("date")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const isAnomaly = anomalyIds && anomalyIds.has(r.id);
              return (
                <tr key={r.id} className={isAnomaly ? "anomaly-row" : ""}>
                  <td data-label={t("crop")}>
                    {r.crop}
                    {r.variety ? ` (${r.variety})` : ""}
                    {isAnomaly && <span className="anomaly-badge">{t("anomaly_badge")}</span>}
                  </td>
                  <td data-label={t("market")}>{r.market}</td>
                  <td data-label={t("district")}>{r.district}</td>
                  <td data-label={t("min_price")}>₹{formatPrice(r.min_price, unit)}</td>
                  <td data-label={t("max_price")}>₹{formatPrice(r.max_price, unit)}</td>
                  <td data-label={t("modal_price")} className="modal-price">
                    ₹{formatPrice(r.modal_price, unit)}
                  </td>
                  <td data-label={t("trend_7d")}>
                    <TrendChart cropId={r.crop_id} marketId={r.market_id} />
                  </td>
                  <td data-label={t("date")}>{r.date}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
