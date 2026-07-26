-- ============================================================================
-- ChatMoney — CLEAN ONE MONTH (July 2026)
-- ----------------------------------------------------------------------------
-- Deletes every transaction DATED in July 2026 from the app tables. Unlike
-- 01_clean.sql (which wipes ALL data), this is scoped to a single month by the
-- `date` column and leaves every other month — and your balance anchors,
-- wallets, and other months' rows — untouched.
--
-- To clean a DIFFERENT month, change the two dates below (start = first of the
-- month, end = first of the NEXT month; the range is [start, end) so it's
-- inclusive of the whole month and never bleeds into the next).
--
-- ⚠️  This is destructive and cannot be undone. It removes:
--       • expenses          dated in July 2026
--       • income            dated in July 2026
--       • wallet_transfers  dated in July 2026   (optional — see note below)
--
--     Consequences to expect:
--       • current_balance = manual_balance + (income − expenses) after the
--         latest balance anchor. Deleting July income/expenses that fall after
--         that anchor WILL change your current balance.
--       • Wallet balances are computed from these same rows, so any wallet that
--         had July movement will change too. The invariant
--         (Σ wallets + unassigned == current_balance) still holds afterward —
--         it's just a smaller total.
--
-- Only ChatMoney app tables are touched; Supabase auth/storage/system tables
-- are NOT affected. Run in the Supabase SQL editor.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- STEP 1 — PREVIEW: see exactly what will be deleted BEFORE deleting anything.
-- Run this SELECT on its own first and eyeball the counts + totals.
-- ---------------------------------------------------------------------------
SELECT 'expenses'         AS table, count(*) AS rows, COALESCE(sum(amount), 0) AS total
    FROM expenses         WHERE date >= '2026-07-01' AND date < '2026-08-01'
UNION ALL
SELECT 'income',          count(*),  COALESCE(sum(amount), 0)
    FROM income           WHERE date >= '2026-07-01' AND date < '2026-08-01'
UNION ALL
SELECT 'wallet_transfers', count(*), COALESCE(sum(amount), 0)
    FROM wallet_transfers WHERE date >= '2026-07-01' AND date < '2026-08-01';

-- ---------------------------------------------------------------------------
-- STEP 2 — DELETE. Once the preview looks right, run the block below.
-- ---------------------------------------------------------------------------
DELETE FROM expenses WHERE date >= '2026-07-01' AND date < '2026-08-01';
DELETE FROM income   WHERE date >= '2026-07-01' AND date < '2026-08-01';

-- Optional: also remove July transfers between wallets. Comment this line out
-- if you only meant income/expenses and want to keep transfer history.
DELETE FROM wallet_transfers WHERE date >= '2026-07-01' AND date < '2026-08-01';

-- ---------------------------------------------------------------------------
-- STEP 3 — VERIFY: all three should now report 0 rows for July.
-- ---------------------------------------------------------------------------
SELECT 'expenses'         AS table, count(*) AS rows_left_in_july
    FROM expenses         WHERE date >= '2026-07-01' AND date < '2026-08-01'
UNION ALL
SELECT 'income',          count(*)
    FROM income           WHERE date >= '2026-07-01' AND date < '2026-08-01'
UNION ALL
SELECT 'wallet_transfers', count(*)
    FROM wallet_transfers WHERE date >= '2026-07-01' AND date < '2026-08-01';
