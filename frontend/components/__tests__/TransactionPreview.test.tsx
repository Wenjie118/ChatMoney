/**
 * Component tests for TransactionPreview (Issue #17, non-planner part).
 *
 * Covers the editable review table's core logic — edit a cell, delete a row,
 * add a row, the save payload (UI-only ids stripped), and the invalid-amount
 * save guard — with the API client mocked.
 *
 * (The SalaryPlan tests from #17 are deferred with the Planner feature, #2 —
 * that component does not exist yet.)
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import TransactionPreview from "@/components/TransactionPreview";
import { saveMultiple } from "@/lib/api";
import type { ITransaction } from "@/lib/types";

// Mock the API client so no real fetch happens; assert on the call payload.
vi.mock("@/lib/api", () => ({ saveMultiple: vi.fn() }));
const mockedSave = vi.mocked(saveMultiple);

function initialRows(): ITransaction[] {
  return [
    { type: "expense", amount: 10, category_or_source: "Food", description: "Lunch", date: "2026-07-01", count: 2 },
    { type: "income", amount: 3000, category_or_source: "Salary", description: "Pay", date: "2026-07-25" },
  ];
}

beforeEach(() => {
  mockedSave.mockReset();
  mockedSave.mockResolvedValue({ total: 2, saved: 2, failed: 0 });
});

describe("TransactionPreview", () => {
  it("renders the initial rows", () => {
    render(<TransactionPreview initialRows={initialRows()} />);
    expect(screen.getByText(/\(2 rows\)/)).toBeInTheDocument();
    expect(screen.getByDisplayValue("Lunch")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Pay")).toBeInTheDocument();
  });

  it("edits a cell", () => {
    render(<TransactionPreview initialRows={initialRows()} />);
    fireEvent.change(screen.getByDisplayValue("Lunch"), { target: { value: "Brunch" } });
    expect(screen.getByDisplayValue("Brunch")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Lunch")).not.toBeInTheDocument();
  });

  it("deletes a row", () => {
    render(<TransactionPreview initialRows={initialRows()} />);
    const deleteButtons = screen.getAllByRole("button", { name: "Delete row" });
    fireEvent.click(deleteButtons[0]);
    expect(screen.getByText(/\(1 rows\)/)).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Lunch")).not.toBeInTheDocument();
  });

  it("adds a blank row", () => {
    render(<TransactionPreview initialRows={initialRows()} />);
    fireEvent.click(screen.getByRole("button", { name: /Add row/ }));
    expect(screen.getByText(/\(3 rows\)/)).toBeInTheDocument();
  });

  it("saves with the expected payload (UI ids stripped) and reports the result", async () => {
    const onSaved = vi.fn();
    const user = userEvent.setup();
    render(<TransactionPreview initialRows={initialRows()} onSaved={onSaved} />);

    await user.click(screen.getByRole("button", { name: /Confirm & Save/ }));

    expect(mockedSave).toHaveBeenCalledTimes(1);
    expect(mockedSave).toHaveBeenCalledWith([
      { type: "expense", amount: 10, category_or_source: "Food", description: "Lunch", date: "2026-07-01", count: 2 },
      { type: "income", amount: 3000, category_or_source: "Salary", description: "Pay", date: "2026-07-25" },
    ]);
    expect(onSaved).toHaveBeenCalledWith({ total: 2, saved: 2, failed: 0 });
    expect(await screen.findByText(/Saved 2 of 2 transactions/)).toBeInTheDocument();
  });

  it("sends edits made in the table in the save payload", async () => {
    const user = userEvent.setup();
    render(<TransactionPreview initialRows={initialRows()} />);

    fireEvent.change(screen.getByDisplayValue("Lunch"), { target: { value: "Brunch" } });
    await user.click(screen.getByRole("button", { name: /Confirm & Save/ }));

    const savedRows = mockedSave.mock.calls[0][0];
    expect(savedRows[0].description).toBe("Brunch");
  });

  it("blocks save when a row's amount is 0 or less and does not call the API", async () => {
    const user = userEvent.setup();
    const rows = initialRows();
    rows[0].amount = 0; // cleared / invalid amount
    render(<TransactionPreview initialRows={rows} />);

    await user.click(screen.getByRole("button", { name: /Confirm & Save/ }));

    expect(mockedSave).not.toHaveBeenCalled();
    expect(screen.getByText(/amount of 0 or less/)).toBeInTheDocument();
  });

  it("blocks save when a row has no category/source and does not call the API", async () => {
    const user = userEvent.setup();
    const rows = initialRows();
    rows[0].category_or_source = ""; // nothing picked in the dropdown
    render(<TransactionPreview initialRows={rows} />);

    await user.click(screen.getByRole("button", { name: /Confirm & Save/ }));

    expect(mockedSave).not.toHaveBeenCalled();
    expect(screen.getByText(/missing a category\/source/)).toBeInTheDocument();
  });

  it("shows the Count column by default (PDF flow)", () => {
    render(<TransactionPreview initialRows={initialRows()} />);
    expect(screen.getByRole("columnheader", { name: "Count" })).toBeInTheDocument();
  });

  it("hides the Count column when showCount is false (manual entry)", () => {
    render(<TransactionPreview initialRows={initialRows()} showCount={false} />);
    expect(screen.queryByRole("columnheader", { name: "Count" })).not.toBeInTheDocument();
  });

  it("uses a custom title and help text when provided", () => {
    render(
      <TransactionPreview
        initialRows={initialRows()}
        title="✏️ Enter transactions"
        helpText="Add a row for each transaction, edit the cells, then save."
      />,
    );
    expect(screen.getByText(/Enter transactions \(2 rows\)/)).toBeInTheDocument();
    expect(screen.getByText(/Add a row for each transaction/)).toBeInTheDocument();
  });
});
