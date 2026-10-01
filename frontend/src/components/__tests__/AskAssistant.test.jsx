import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "../../i18n";
import AskAssistant from "../AskAssistant";
import { api } from "../../api";

jest.mock("../../api", () => ({
  api: { ask: jest.fn() },
}));

describe("AskAssistant", () => {
  beforeEach(() => {
    api.ask.mockReset();
  });

  it("disables the submit button until a question is typed", () => {
    render(<AskAssistant />);
    expect(screen.getByRole("button", { name: /ask/i })).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "onion price?" } });
    expect(screen.getByRole("button", { name: /ask/i })).not.toBeDisabled();
  });

  it("shows the answer once the API call resolves", async () => {
    api.ask.mockResolvedValue({
      answer: "Onion is Rs 1800/quintal in Hyderabad today.",
      assistant_enabled: true,
      matched: { crop: "Onion", state: null, district: "Hyderabad" },
      records_used: 3,
    });

    render(<AskAssistant />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "onion price in Hyderabad" } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() =>
      expect(screen.getByText(/Onion is Rs 1800\/quintal/)).toBeInTheDocument()
    );
    expect(api.ask).toHaveBeenCalledWith("onion price in Hyderabad", expect.any(String), []);
  });

  it("shows a degraded-mode note when the assistant isn't fully configured", async () => {
    api.ask.mockResolvedValue({
      answer: "Latest: Tomato ... [AI summary unavailable — showing raw latest record instead.]",
      assistant_enabled: false,
      matched: {},
      records_used: 1,
    });

    render(<AskAssistant />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "tomato price" } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() => expect(screen.getByText(/not fully configured/i)).toBeInTheDocument());
  });

  it("shows an error message if the API call fails", async () => {
    api.ask.mockRejectedValue(new Error("network error"));

    render(<AskAssistant />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "tomato price" } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() => expect(screen.getByText(/could not get an answer/i)).toBeInTheDocument());
  });
  it("sends earlier turns as history so follow-up questions work", async () => {
    api.ask
      .mockResolvedValueOnce({ answer: "Rs 1800 in Hyderabad.", assistant_enabled: true, sources: [] })
      .mockResolvedValueOnce({ answer: "Rs 1700 in Warangal.", assistant_enabled: true, sources: [] });

    render(<AskAssistant />);
    const box = screen.getByRole("textbox");

    fireEvent.change(box, { target: { value: "onion price in Hyderabad" } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));
    await waitFor(() => expect(screen.getByText(/Rs 1800 in Hyderabad/)).toBeInTheDocument());

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "and in Warangal?" } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));
    await waitFor(() => expect(screen.getByText(/Rs 1700 in Warangal/)).toBeInTheDocument());

    expect(api.ask).toHaveBeenLastCalledWith("and in Warangal?", expect.any(String), [
      { role: "user", content: "onion price in Hyderabad" },
      { role: "assistant", content: "Rs 1800 in Hyderabad." },
    ]);
    // the first exchange stays visible
    expect(screen.getByText(/Rs 1800 in Hyderabad/)).toBeInTheDocument();
  });

  it("lists the price records an answer was based on", async () => {
    api.ask.mockResolvedValue({
      answer: "Onion pays best at Bowenpally.",
      assistant_enabled: true,
      sources: [
        { crop: "Onion", market: "Bowenpally", district: "Hyderabad", modal_price: 1800, date: "2026-10-01" },
      ],
    });

    render(<AskAssistant />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "best market for onion" } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() => expect(screen.getByText(/Based on 1 price records/i)).toBeInTheDocument());
    expect(screen.getByText(/Bowenpally, Hyderabad — Rs 1800\/quintal \(2026-10-01\)/)).toBeInTheDocument();
  });

  it("clears the conversation when starting a new chat", async () => {
    api.ask.mockResolvedValue({ answer: "Rs 1800.", assistant_enabled: true, sources: [] });

    render(<AskAssistant />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "onion price" } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));
    await waitFor(() => expect(screen.getByText(/Rs 1800\./)).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /start new chat/i }));
    expect(screen.queryByText(/Rs 1800\./)).not.toBeInTheDocument();
  });

  it("hides voice controls when the browser has no speech support", () => {
    render(<AskAssistant />);
    expect(screen.queryByRole("button", { name: /speak your question/i })).not.toBeInTheDocument();
  });
});
