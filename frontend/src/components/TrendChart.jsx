import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../api";

/**
 * Small inline sparkline for a single crop/market row. This wires up
 * `/api/prices/trend` and the `api.trend()` client method, both of
 * which existed in the original scaffold but were never rendered
 * anywhere in the UI.
 */
export default function TrendChart({ cropId, marketId }) {
  const { t } = useTranslation();
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .trend(cropId, marketId, 7)
      .then((rows) => {
        if (!cancelled) setData(rows);
      })
      .catch(() => {
        if (!cancelled) setData([]);
      });
    return () => {
      cancelled = true;
    };
  }, [cropId, marketId]);

  if (!data || data.length < 2) return null;

  return (
    <div className="trend-chart" title={t("trend_7d")}>
      <ResponsiveContainer width={100} height={32}>
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="modal_price"
            stroke="var(--green)"
            strokeWidth={2}
            dot={false}
          />
          <XAxis dataKey="date" hide />
          <YAxis hide domain={["auto", "auto"]} />
          <Tooltip
            formatter={(value) => [`₹${value}`, t("modal_price")]}
            labelFormatter={(label) => label}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
