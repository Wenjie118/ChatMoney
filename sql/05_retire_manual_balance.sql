-- ============================================================================
-- ChatMoney — RETIRE THE MANUAL BALANCE
-- ----------------------------------------------------------------------------
-- Optional cleanup. The app no longer reads `balance.manual_balance` at all:
--
--     current_balance = Σ(active wallet balances) + unassigned
--
-- Before this change, the latest manual_balance acted as a standalone baseline
-- that wallets stacked on TOP of, so the headline balance never equalled the sum
-- of your wallets (it was over by exactly that baseline). The code fix already
-- makes the number correct — this script just clears the stale figure out of the
-- table so nobody reads it later and gets confused.
--
-- ⚠️  DO **NOT** DELETE THE BALANCE ROW. ⚠️
--     Its `created_at` is still load-bearing: it is the WALLET-ERA ANCHOR, the
--     horizon that keeps pre-wallet history out of the sums. Only movements
--     recorded strictly after it count toward wallets and the balance.
--     Delete the row and every older transaction floods back in — for this
--     database that is 43 income + 364 expense rows that would land in
--     Unassigned and inflate the balance by tens of thousands of RM.
--     We only ZERO the amount; the row (and its timestamp) stays.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- STEP 1 — PREVIEW: the anchor row(s) as they stand today.
-- The newest row is the live anchor; older ones are inert history.
-- ---------------------------------------------------------------------------
SELECT id, manual_balance, last_updated, created_at
    FROM balance
    ORDER BY created_at DESC;

-- ---------------------------------------------------------------------------
-- STEP 2 — ZERO the amounts, keeping every row and every created_at intact.
-- ---------------------------------------------------------------------------
UPDATE balance SET manual_balance = 0 WHERE manual_balance <> 0;

-- ---------------------------------------------------------------------------
-- STEP 3 — VERIFY: same rows, same timestamps, all amounts now 0.
-- Your balance in the app is unchanged by this script (it already ignores the
-- column) and should read as the sum of your wallets.
-- ---------------------------------------------------------------------------
SELECT id, manual_balance, last_updated, created_at
    FROM balance
    ORDER BY created_at DESC;
