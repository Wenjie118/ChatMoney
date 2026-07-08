-- ============================================================================
-- ChatMoney — CLEANUP SCRIPT
-- ----------------------------------------------------------------------------
-- Run this FIRST in the Supabase SQL editor to wipe ALL rows from the three
-- app tables and reset their id counters back to 1.
--
-- ⚠️  THIS DELETES EVERYTHING in expenses, income and balance (your current
--     data included). Only the ChatMoney app tables are touched — Supabase
--     auth/storage/system tables are NOT affected.
-- ============================================================================

TRUNCATE TABLE expenses, income, balance RESTART IDENTITY;

-- Sanity check — all three should report 0.
SELECT 'expenses' AS table, count(*) AS rows FROM expenses
UNION ALL SELECT 'income',   count(*) FROM income
UNION ALL SELECT 'balance',  count(*) FROM balance;
