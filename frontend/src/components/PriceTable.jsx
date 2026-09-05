import React from "react";
import { useTranslation } from "react-i18next";

export default function PriceTable({ rows, loading }) {
  const { t } = useTranslation();

  if (loading) return <p className="status-msg">{t("loading")}</p>;
  if (!rows || rows.length === 0) return <p className="status-msg">{t("no_data")}</p>;

  return (
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
            <th>{t("date")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td data-label={t("crop")}>{r.crop}{r.variety ? ` (${r.variety})` : ""}</td>
              <td data-label={t("market")}>{r.market}</td>
              <td data-label={t("district")}>{r.district}</td>
              <td data-label={t("min_price")}>₹{r.min_price ?? "—"}</td>
              <td data-label={t("max_price")}>₹{r.max_price ?? "—"}</td>
              <td data-label={t("modal_price")} className="modal-price">₹{r.modal_price ?? "—"}</td>
              <td data-label={t("date")}>{r.date}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
