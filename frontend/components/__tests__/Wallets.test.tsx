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
import { getWallets, getUnassigned, createWallet, setWalletBalance } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getWallets: vi.fn(),
  getUnassigned: vi.fn(),
  createWallet: vi.fn(),
  renameWallet: vi.fn(),
  deleteWallet: vi.fn(),
  setWalletBalance: vi.fn(),
  createTransfer: vi.fn(),
  getWalletLedger: vi.fn(),
  resolveTransactionWallet: vi.fn(),
}));

const mGetWallets = vi.mocked(getWallets);
const mGetUnassigned = vi.mocked(getUnassigned);
const mCreate = vi.mocked(createWallet);
const mSetBalance = vi.mocked(setWalletBalance);

beforeEach(() => {
  vi.clearAllMocks();
  mGetWallets.mockResolvedValue([{ id: 1, name: "Daily", balance: 250 }]);
  mGetUnassigned.mockResolvedValue({ total: 0, rows: [] });
});

describe("Wallets", () => {
  it("renders wallet cards with computed balances", async () => {
    render(<Wallets />);
    expect(await screen.findByText("Daily")).toBeInTheDocument();
    // 250 appears on the wallet card AND the "Total across wallets" card (1 wallet).
    expect(screen.getAllByText("RM 250.00").length).toBeGreaterThanOrEqual(1);
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

  it("shows the total across wallets", async () => {
    mGetWallets.mockResolvedValue([
      { id: 1, name: "Daily", balance: 250 },
      { id: 2, name: "Savings", balance: 1000 },
    ]);
    render(<Wallets />);
    // "Daily" also appears in the transfer dropdowns (2 wallets), so wait on the
    // unique total-card heading instead. 1250 is unique (only the total).
    await screen.findByText("Total across wallets");
    expect(screen.getByText("RM 1250.00")).toBeInTheDocument();
  });

  it("corrects a wallet balance and reloads", async () => {
    const user = userEvent.setup();
    mSetBalance.mockResolvedValue({ id: 1, name: "Daily", balance: 400 });
    render(<Wallets />);
    await screen.findByText("Daily");

    await user.click(screen.getByRole("button", { name: "Set balance" }));
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "400" } });
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(mSetBalance).toHaveBeenCalledWith(1, 400));
    expect(mGetWallets).toHaveBeenCalledTimes(2); // reload after set
  });

  it("disables deleting the only wallet", async () => {
    render(<Wallets />);
    await screen.findByText("Daily");
    // Single wallet -> its delete button is disabled (keep at least one).
    expect(screen.getByRole("button", { name: /Delete Daily/ })).toBeDisabled();
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
