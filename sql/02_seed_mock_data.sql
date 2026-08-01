-- ============================================================================
-- ChatMoney — MOCK DATA SEED
-- ----------------------------------------------------------------------------
-- Run this AFTER 01_clean.sql in the Supabase SQL editor.
--
-- Generates ~1 year of realistic Malaysian (RM) transactions:
--   • Range: 2025-06-01 .. 2026-05-28   (June 2026 onward is LEFT EMPTY for
--     your own real data — nothing here spills past May 2026).
--   • Income:  monthly salary + occasional side income + monthly savings interest.
--   • Expenses: recurring bills + Food / Transport / Shopping / Entertainment /
--     Health / Other, spread randomly through each month.
--   • Categories/sources match exactly what the app + LLM expect.
--
-- created_at is set explicitly (aligned to each transaction's date) so the
-- computed "current balance" in db.py is deterministic, not dependent on
-- insertion order.
--
-- Balance model (db.py): current_balance = Σ(active wallet balances) + unassigned,
-- both summed over movements with created_at > balance.created_at. The balance row
-- below is therefore an ANCHOR (a horizon), not money — its manual_balance is
-- never read. We anchor it at 2025-05-31, before all mock data, so every seeded
-- transaction counts: the app shows all mock income - all mock expenses, sitting
-- in Unassigned until you create wallets and assign it.
-- ============================================================================

-- Horizon anchor placed just BEFORE the mock history begins. The amount is 0
-- because manual_balance is no longer money — only created_at matters here.
INSERT INTO balance (manual_balance, last_updated, created_at)
VALUES (0, DATE '2025-05-31', TIMESTAMP '2025-05-31 08:00:00');

DO $$
DECLARE
  m           date;
  dd          int;
  k           int;
  cnt         int;

  food_desc   text[] := ARRAY['Groceries at Jaya Grocer','Lunch at mamak','Dinner with friends',
                              'Starbucks coffee','McDonald''s','Nasi lemak breakfast',
                              'Grab food delivery','Tesco groceries','Bubble tea','Chicken rice'];
  trans_desc  text[] := ARRAY['Petrol','Grab ride','Touch n Go reload','Parking',
                              'LRT/MRT top-up','Car service'];
  shop_desc   text[] := ARRAY['Uniqlo clothes','Shopee order','Lazada order','New shoes',
                              'Home supplies','Electronics'];
  ent_desc    text[] := ARRAY['Cinema tickets','Netflix subscription','Spotify',
                              'Concert tickets','Games','Karaoke night'];
  health_desc text[] := ARRAY['Pharmacy','Clinic visit','Gym membership','Vitamins','Dental checkup'];
  other_desc  text[] := ARRAY['Gift for a friend','Charity donation','Miscellaneous','Cash withdrawal'];
BEGIN
  FOR m IN
    SELECT generate_series(DATE '2025-06-01', DATE '2026-05-01', INTERVAL '1 month')::date
  LOOP
    -- ================= INCOME =================
    -- Salary on the 25th
    INSERT INTO income (amount, source, description, date, created_at)
    VALUES (round((4200 + random()*800)::numeric, 2), 'Salary', 'Monthly salary',
            m + 24, (m + 24) + TIME '09:00');

    -- Occasional side income (~half the months)
    IF random() < 0.5 THEN
      INSERT INTO income (amount, source, description, date, created_at)
      VALUES (round((200 + random()*600)::numeric, 2), 'Transfer', 'Freelance / side income',
              m + 14, (m + 14) + TIME '15:00');
    END IF;

    -- Small savings interest every month
    INSERT INTO income (amount, source, description, date, created_at)
    VALUES (round((3 + random()*20)::numeric, 2), 'Interest', 'Savings interest',
            m + 27, (m + 27) + TIME '23:00');

    -- ================= RECURRING BILLS =================
    INSERT INTO expenses (amount, category, description, date, created_at) VALUES
      (round((900 + random()*100)::numeric, 2), 'Bills', 'Rent',              m + 1, (m + 1) + TIME '10:00'),
      (round(( 80 + random()* 90)::numeric, 2), 'Bills', 'Electricity (TNB)', m + 5, (m + 5) + TIME '10:00'),
      (round(( 20 + random()* 20)::numeric, 2), 'Bills', 'Water bill',        m + 5, (m + 5) + TIME '10:05'),
      (129.00,                                  'Bills', 'Unifi internet',    m + 7, (m + 7) + TIME '10:00'),
      (round(( 50 + random()* 50)::numeric, 2), 'Bills', 'Phone bill',        m + 7, (m + 7) + TIME '10:10');

    -- ================= FOOD (8-12 / month) =================
    cnt := 8 + floor(random()*5)::int;
    FOR k IN 1..cnt LOOP
      dd := floor(random()*28)::int;
      INSERT INTO expenses (amount, category, description, date, created_at)
      VALUES (round((8 + random()*45)::numeric, 2), 'Food',
              food_desc[1 + floor(random()*array_length(food_desc,1))::int],
              m + dd, (m + dd) + TIME '12:30');
    END LOOP;

    -- ================= TRANSPORT (4-7 / month) =================
    cnt := 4 + floor(random()*4)::int;
    FOR k IN 1..cnt LOOP
      dd := floor(random()*28)::int;
      INSERT INTO expenses (amount, category, description, date, created_at)
      VALUES (round((5 + random()*70)::numeric, 2), 'Transport',
              trans_desc[1 + floor(random()*array_length(trans_desc,1))::int],
              m + dd, (m + dd) + TIME '08:00');
    END LOOP;

    -- ================= SHOPPING (1-4 / month) =================
    cnt := 1 + floor(random()*4)::int;
    FOR k IN 1..cnt LOOP
      dd := floor(random()*28)::int;
      INSERT INTO expenses (amount, category, description, date, created_at)
      VALUES (round((20 + random()*180)::numeric, 2), 'Shopping',
              shop_desc[1 + floor(random()*array_length(shop_desc,1))::int],
              m + dd, (m + dd) + TIME '16:00');
    END LOOP;

    -- ================= ENTERTAINMENT (1-3 / month) =================
    cnt := 1 + floor(random()*3)::int;
    FOR k IN 1..cnt LOOP
      dd := floor(random()*28)::int;
      INSERT INTO expenses (amount, category, description, date, created_at)
      VALUES (round((15 + random()*85)::numeric, 2), 'Entertainment',
              ent_desc[1 + floor(random()*array_length(ent_desc,1))::int],
              m + dd, (m + dd) + TIME '20:00');
    END LOOP;

    -- ================= HEALTH (0-2 / month) =================
    cnt := floor(random()*3)::int;
    FOR k IN 1..cnt LOOP
      dd := floor(random()*28)::int;
      INSERT INTO expenses (amount, category, description, date, created_at)
      VALUES (round((20 + random()*150)::numeric, 2), 'Health',
              health_desc[1 + floor(random()*array_length(health_desc,1))::int],
              m + dd, (m + dd) + TIME '11:00');
    END LOOP;

    -- ================= OTHER (0-2 / month) =================
    cnt := floor(random()*3)::int;
    FOR k IN 1..cnt LOOP
      dd := floor(random()*28)::int;
      INSERT INTO expenses (amount, category, description, date, created_at)
      VALUES (round((10 + random()*120)::numeric, 2), 'Other',
              other_desc[1 + floor(random()*array_length(other_desc,1))::int],
              m + dd, (m + dd) + TIME '14:00');
    END LOOP;

  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- Summary of what was generated (per month).
-- ---------------------------------------------------------------------------
SELECT
  to_char(d.mth, 'YYYY-MM')                                   AS month,
  count(*) FILTER (WHERE d.kind = 'income')                   AS income_rows,
  count(*) FILTER (WHERE d.kind = 'expense')                  AS expense_rows,
  round((sum(d.amount) FILTER (WHERE d.kind = 'income'))::numeric,  2)   AS total_income,
  round((sum(d.amount) FILTER (WHERE d.kind = 'expense'))::numeric, 2)   AS total_expenses
FROM (
  SELECT date_trunc('month', date)::date AS mth, 'income'  AS kind, amount FROM income
  UNION ALL
  SELECT date_trunc('month', date)::date AS mth, 'expense' AS kind, amount FROM expenses
) d
GROUP BY d.mth
ORDER BY d.mth;
