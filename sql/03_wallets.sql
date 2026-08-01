-- ============================================================================
-- ChatMoney — WALLETS MIGRATION
-- ----------------------------------------------------------------------------
-- Run this ONCE in the Supabase SQL editor to add the virtual-wallet system.
-- Idempotent (IF NOT EXISTS), so re-running is safe.
--
-- A "wallet" is a named virtual container for money. Balances are COMPUTED from
-- a ledger (tagged income/expenses + transfers), never stored — mirroring the
-- existing main-balance model in db.py. There is deliberately NO balance column.
--
-- The invariant the app relies on:
--     Σ(active wallet balances) + unassigned == current_balance
-- get_balance() DEFINES the balance as that sum, so it holds by construction.
-- Both sides are computed over movements recorded after the latest `balance` row
-- (the wallet-era anchor — a horizon only; its manual_balance is not read; see
-- 05_retire_manual_balance.sql). Money tagged to a NULL wallet OR a soft-deleted
-- wallet counts toward Unassigned, so nothing is lost or double-counted.
-- ============================================================================

-- Named virtual wallets. Soft-delete only (is_active = false); never hard-delete,
-- so historical ledger rows stay valid.
CREATE TABLE IF NOT EXISTS wallets (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Internal money movements between wallets. A transfer is NOT income and NOT an
-- expense — it nets to zero across the system (money changing label).
-- from_wallet / to_wallet are nullable ONLY so PDF import can record a movement
-- whose wallet couldn't be inferred; the manual API path requires both.
CREATE TABLE IF NOT EXISTS wallet_transfers (
    id            BIGSERIAL PRIMARY KEY,
    from_wallet   BIGINT REFERENCES wallets(id),
    to_wallet     BIGINT REFERENCES wallets(id),
    amount        REAL NOT NULL CHECK (amount > 0),
    description   TEXT,
    date          DATE NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Tag existing transaction tables to a wallet. Nullable so historical rows (and
-- PDF-imported rows with an unknown wallet) remain valid; NULL rows surface in
-- the app's "Unassigned" bucket.
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS wallet_id BIGINT REFERENCES wallets(id);
ALTER TABLE income   ADD COLUMN IF NOT EXISTS wallet_id BIGINT REFERENCES wallets(id);

-- Speed up the per-wallet ledger sums.
CREATE INDEX IF NOT EXISTS idx_expenses_wallet_id ON expenses(wallet_id);
CREATE INDEX IF NOT EXISTS idx_income_wallet_id   ON income(wallet_id);
CREATE INDEX IF NOT EXISTS idx_transfers_from     ON wallet_transfers(from_wallet);
CREATE INDEX IF NOT EXISTS idx_transfers_to       ON wallet_transfers(to_wallet);

-- Sanity check — should list the two new tables (0 rows each initially).
SELECT 'wallets' AS obj, count(*) AS n FROM wallets
UNION ALL SELECT 'wallet_transfers', count(*) FROM wallet_transfers;
