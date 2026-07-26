/**
 * Component tests for ChatInterface — the manual-entry path (Issue #38).
 *
 * Covers the third upload method: opening the editable table with NO PDF and NO
 * LLM, and that Confirm & Save posts via /transactions/save-multiple, drops a
 * confirmation into the chat, and closes the table. The API client is mocked, so
 * no real fetch happens. (BusyProvider is intentionally omitted — useBusy()
 * falls back to a no-op with no provider, which is the /chat-route case.)
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ChatInterface from "@/components/ChatInterface";
import { saveMultiple } from "@/lib/api";

// Mock the whole API client: ChatInterface uses parse* + getWallets (on mount),
// TransactionPreview uses saveMultiple. Only saveMultiple is exercised here;
// getWallets resolves to [] so the manual-entry table has no wallet column.
vi.mock("@/lib/api", () => ({
  parseTransaction: vi.fn(),
  parsePDF: vi.fn(),
  saveMultiple: vi.fn(),
  getWallets: vi.fn(() => Promise.resolve([])),
}));
const mockedSave = vi.mocked(saveMultiple);

beforeEach(() => {
  mockedSave.mockReset();
  mockedSave.mockResolvedValue({ total: 1, saved: 1, failed: 0 });
});

describe("ChatInterface — manual entry", () => {
  it("reveals a one-row table without a Count column when opened", async () => {
    const user = userEvent.setup();
    render(<ChatInterface />);

    // Closed by default.
    expect(screen.queryByText(/Enter transactions/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Add transactions manually/ }));

    // Seeded with exactly one blank row, and no PDF-merge Count column.
    expect(screen.getByText(/Enter transactions \(1 rows\)/)).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Count" })).not.toBeInTheDocument();
  });

  it("saves manual rows, confirms in the chat, and closes the table", async () => {
    const user = userEvent.setup();
    render(<ChatInterface />);

    await user.click(screen.getByRole("button", { name: /Add transactions manually/ }));

    // A fresh row starts with an empty amount and no category — set both before saving,
    // else the amount / category guards block it. The category <select> is the
    // second combobox (the first is the expense/income type).
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "50" } });
    await user.selectOptions(screen.getAllByRole("combobox")[1], "Food");
    await user.click(screen.getByRole("button", { name: /Confirm & Save/ }));

    expect(mockedSave).toHaveBeenCalledTimes(1);
    expect(mockedSave.mock.calls[0][0][0].amount).toBe(50);
    expect(mockedSave.mock.calls[0][0][0].category_or_source).toBe("Food");

    // Confirmation lands in the chat, and the table closes.
    expect(await screen.findByText(/Saved 1 of 1 transactions/)).toBeInTheDocument();
    expect(screen.queryByText(/Enter transactions/)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Add transactions manually/ }),
    ).toBeInTheDocument();
  });
});
