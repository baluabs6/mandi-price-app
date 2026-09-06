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
    expect(api.ask).toHaveBeenCalledWith("onion price in Hyderabad", expect.any(String));
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
});
