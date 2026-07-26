-- ============================================================================
-- ChatMoney — CLEANUP SCRIPT
-- ----------------------------------------------------------------------------
-- Run this FIRST in the Supabase SQL editor to wipe ALL rows from the three
-- app tables and reset their id counters back to 1.
--
-- ⚠️  THIS DELETES EVERYTHING in expenses, income, balance, wallets and
--     wallet_transfers (your current data included). Only the ChatMoney app
--     tables are touched — Supabase auth/storage/system tables are NOT affected.
--
-- NOTE: wallets/wallet_transfers only exist after running 03_wallets.sql.
-- CASCADE clears the FK links (expenses.wallet_id / income.wallet_id) safely.
-- ============================================================================

TRUNCATE TABLE expenses, income, balance, wallet_transfers, wallets
    RESTART IDENTITY CASCADE;

-- Sanity check — all should report 0.
SELECT 'expenses' AS table, count(*) AS rows FROM expenses
UNION ALL SELECT 'income',           count(*) FROM income
UNION ALL SELECT 'balance',          count(*) FROM balance
UNION ALL SELECT 'wallets',          count(*) FROM wallets
UNION ALL SELECT 'wallet_transfers', count(*) FROM wallet_transfers;
