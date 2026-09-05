import React from "react";
import { useTranslation } from "react-i18next";

export default function FilterBar({
  states,
  districts,
  crops,
  stateId,
  districtId,
  cropId,
  onStateChange,
  onDistrictChange,
  onCropChange,
}) {
  const { t } = useTranslation();

  return (
    <div className="filter-bar">
      <label>
        {t("select_state")}
        <select value={stateId || ""} onChange={(e) => onStateChange(e.target.value || null)}>
          <option value="">{t("all")}</option>
          {states.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        {t("select_district")}
        <select value={districtId || ""} onChange={(e) => onDistrictChange(e.target.value || null)}>
          <option value="">{t("all")}</option>
          {districts.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        {t("select_crop")}
        <select value={cropId || ""} onChange={(e) => onCropChange(e.target.value || null)}>
          <option value="">{t("all")}</option>
          {crops.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
