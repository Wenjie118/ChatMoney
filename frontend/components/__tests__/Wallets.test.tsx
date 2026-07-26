/**
 * Component tests for the Wallets tab.
 *
 * The API client is mocked, so no real fetch happens. Covers: rendering wallet
 * cards with computed balances, the Unassigned card appearing only when non-zero,
 * and the create-wallet flow calling the API + reloading.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import Wallets from "@/components/Wallets";
import { getWallets, getUnassigned, createWallet } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getWallets: vi.fn(),
  getUnassigned: vi.fn(),
  createWallet: vi.fn(),
  renameWallet: vi.fn(),
  deleteWallet: vi.fn(),
  createTransfer: vi.fn(),
  getWalletLedger: vi.fn(),
  resolveTransactionWallet: vi.fn(),
}));

const mGetWallets = vi.mocked(getWallets);
const mGetUnassigned = vi.mocked(getUnassigned);
const mCreate = vi.mocked(createWallet);

beforeEach(() => {
  vi.clearAllMocks();
  mGetWallets.mockResolvedValue([{ id: 1, name: "Daily", balance: 250 }]);
  mGetUnassigned.mockResolvedValue({ total: 0, rows: [] });
});

describe("Wallets", () => {
  it("renders wallet cards with computed balances", async () => {
    render(<Wallets />);
    expect(await screen.findByText("Daily")).toBeInTheDocument();
    expect(screen.getByText("RM 250.00")).toBeInTheDocument();
  });

  it("shows the Unassigned card only when the total is non-zero", async () => {
    mGetUnassigned.mockResolvedValue({ total: 1000, rows: [] });
    render(<Wallets />);
    expect(await screen.findByText(/Unassigned/)).toBeInTheDocument();
    expect(screen.getByText("RM 1000.00")).toBeInTheDocument();
  });

  it("hides the Unassigned card when the total is zero", async () => {
    render(<Wallets />);
    await screen.findByText("Daily"); // wait for load
    expect(screen.queryByText(/🟡 Unassigned/)).not.toBeInTheDocument();
  });

  it("creates a wallet and reloads", async () => {
    const user = userEvent.setup();
    mCreate.mockResolvedValue({ id: 2, name: "Savings", balance: 0 });
    render(<Wallets />);
    await screen.findByText("Daily");

    fireEvent.change(screen.getByPlaceholderText(/Savings, Rent, Fun/), {
      target: { value: "Savings" },
    });
    await user.click(screen.getByRole("button", { name: /Create/ }));

    await waitFor(() => expect(mCreate).toHaveBeenCalledWith("Savings"));
    // reload() re-fetches wallets after the create.
    expect(mGetWallets).toHaveBeenCalledTimes(2);
  });
});
