-- ============================================================================
-- ChatMoney — WALLET ADJUSTMENTS
-- ----------------------------------------------------------------------------
-- Run this ONCE in the Supabase SQL editor. Idempotent (IF NOT EXISTS + a guarded
-- migration), so re-running is safe.
--
-- WHY: correcting a wallet ("this wallet should actually hold RM 500") used to be
-- recorded as an income or expense row tagged "Other". That is real money, so the
-- balance was right — but it is NOT a budget event, and it polluted every report
-- that reads the income/expenses tables: the monthly summary, the category
-- charts, the recent-transactions table, and the AI advisor's savings rate.
--
-- An adjustment is a third kind of movement, alongside transactions and transfers:
--   • income / expense  → money entering or leaving your life  (a budget event)
--   • transfer          → money changing wallet                (nets to zero)
--   • adjustment        → a correction to what a wallet holds  (NOT a budget event)
--
-- Adjustments live in their own table, so they count toward wallet balances and
-- the overall balance while being invisible to every income/expense report.
-- ============================================================================

-- `amount` is SIGNED: positive raises the wallet, negative lowers it. (Transfers
-- encode direction with from_wallet/to_wallet; an adjustment has only one side,
-- so the sign carries it.) wallet_id is nullable to match the other ledger
-- tables — a NULL-wallet adjustment falls into Unassigned like anything else.
CREATE TABLE IF NOT EXISTS wallet_adjustments (
    id           BIGSERIAL PRIMARY KEY,
    wallet_id    BIGINT REFERENCES wallets(id),
    amount       REAL NOT NULL CHECK (amount <> 0),
    description  TEXT,
    date         DATE NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_adjustments_wallet_id ON wallet_adjustments(wallet_id);

-- ---------------------------------------------------------------------------
-- STEP 1 — PREVIEW: the adjustment rows currently mis-filed as income/expenses.
-- Run this on its own first. Everything listed here is inflating your monthly
-- summary and the advisor's numbers right now.
-- ---------------------------------------------------------------------------
SELECT 'income' AS from_table, id, amount AS signed_amount, date, wallet_id
    FROM income   WHERE description = 'Wallet balance adjustment'
UNION ALL
SELECT 'expenses', id, -amount, date, wallet_id
    FROM expenses WHERE description = 'Wallet balance adjustment'
ORDER BY date, id;

-- ---------------------------------------------------------------------------
-- STEP 2 — MIGRATE. Copies those rows into wallet_adjustments, then deletes the
-- originals. created_at is PRESERVED, which matters: it is what the balance
-- horizon filters on, so every wallet balance comes out identical afterward.
-- Income becomes a positive adjustment, an expense a negative one.
--
-- Guarded by NOT EXISTS so re-running this file can't duplicate the rows.
-- ---------------------------------------------------------------------------
INSERT INTO wallet_adjustments (wallet_id, amount, description, date, created_at)
SELECT i.wallet_id, i.amount, 'Wallet balance adjustment', i.date, i.created_at
    FROM income i
    WHERE i.description = 'Wallet balance adjustment'
      AND NOT EXISTS (
          SELECT 1 FROM wallet_adjustments a
          WHERE a.created_at = i.created_at AND a.amount = i.amount
      );

INSERT INTO wallet_adjustments (wallet_id, amount, description, date, created_at)
SELECT e.wallet_id, -e.amount, 'Wallet balance adjustment', e.date, e.created_at
    FROM expenses e
    WHERE e.description = 'Wallet balance adjustment'
      AND NOT EXISTS (
          SELECT 1 FROM wallet_adjustments a
          WHERE a.created_at = e.created_at AND a.amount = -e.amount
      );

DELETE FROM income   WHERE description = 'Wallet balance adjustment';
DELETE FROM expenses WHERE description = 'Wallet balance adjustment';

-- ---------------------------------------------------------------------------
-- STEP 3 — VERIFY. The first two counts must be 0 (nothing left mis-filed); the
-- third lists the migrated adjustments.
--
-- Your wallet balances and current_balance are UNCHANGED by this migration —
-- the same money is simply counted from a different table. What changes is the
-- monthly summary / charts / advisor, which no longer see these as real income
-- or spending.
-- ---------------------------------------------------------------------------
SELECT 'income still mis-filed'   AS check_name, count(*) AS n
    FROM income   WHERE description = 'Wallet balance adjustment'
UNION ALL
SELECT 'expenses still mis-filed', count(*)
    FROM expenses WHERE description = 'Wallet balance adjustment';

SELECT id, wallet_id, amount, date, created_at FROM wallet_adjustments ORDER BY created_at;
