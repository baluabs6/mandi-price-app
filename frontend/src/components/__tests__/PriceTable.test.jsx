import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "../../i18n"; // initializes i18next before component render
import PriceTable from "../PriceTable";

// TrendChart makes a network call via api.trend(); stub it out so these
// are pure unit tests of PriceTable's own rendering logic.
jest.mock("../TrendChart", () => () => <div data-testid="trend-chart-stub" />);

const sampleRows = [
  {
    id: 1,
    crop_id: 10,
    market_id: 20,
    crop: "Tomato",
    variety: "Local",
    market: "Bowenpally",
    district: "Hyderabad",
    min_price: 1350,
    max_price: 1450,
    modal_price: 1400,
    date: "2026-09-01",
  },
];

describe("PriceTable", () => {
  it("shows a loading message while loading", () => {
    render(<PriceTable rows={[]} loading={true} />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows a no-data message when there are no rows", () => {
    render(<PriceTable rows={[]} loading={false} />);
    expect(screen.getByText(/no price data/i)).toBeInTheDocument();
  });

  it("renders a row with prices in Rs/quintal by default", () => {
    render(<PriceTable rows={sampleRows} loading={false} anomalyIds={new Set()} />);
    expect(screen.getByText("Tomato (Local)")).toBeInTheDocument();
    expect(screen.getByText("₹1400")).toBeInTheDocument();
  });

  it("converts prices to per-kg when the unit toggle is checked", () => {
    render(<PriceTable rows={sampleRows} loading={false} anomalyIds={new Set()} />);
    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    // 1400 Rs/quintal -> 14.00 Rs/kg
    expect(screen.getByText("₹14.00")).toBeInTheDocument();
  });

  it("shows an anomaly badge for flagged rows", () => {
    render(<PriceTable rows={sampleRows} loading={false} anomalyIds={new Set([1])} />);
    expect(screen.getByText(/unusual price/i)).toBeInTheDocument();
  });

  it("does not show an anomaly badge for unflagged rows", () => {
    render(<PriceTable rows={sampleRows} loading={false} anomalyIds={new Set()} />);
    expect(screen.queryByText(/unusual price/i)).not.toBeInTheDocument();
  });
});
