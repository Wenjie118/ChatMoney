"""
Transaction helper logic that does NOT belong in db.py or llm.py.

WHY THIS FILE EXISTS
    Your old Streamlit `app.py` contained a function `consolidate_transactions()`
    that merged duplicate rows parsed from a PDF (same type/description/category →
    sum the amounts, count how many were merged). Since `app.py` is being deleted
    and we're told to keep db.py / llm.py unchanged, that logic needs a new home.
    This is it.

    Port the body over from the old app.py. The reference implementation grouped
    by (type, description, category-or-source), summed `amount`, kept a `Count`,
    and used the latest date among merged rows.
"""

def consolidate_transactions(transactions: list[dict]) -> list[dict]:
    """Merge identical transactions parsed from a PDF and sum their amounts.

    Args:
        transactions: raw dicts from `llm.parse_pdf_transactions`, each shaped like
            {type, amount, category|source, description, date}. Note the LLM emits
            `category` for expenses and `source` for income — different keys.

    Returns:
        A list of consolidated dicts. We deliberately output the SAME snake_case
        shape the rest of the app already speaks (matches `TransactionResponse` and
        the `ITransaction` TypeScript type), plus a `count` of how many lines merged:

            {type, amount, category_or_source, description, date, count}

        Keeping one transaction shape everywhere means the frontend preview table,
        the save endpoint, and this function all agree — no per-endpoint renaming.

    Logic (ported from the old Streamlit app.py):
        1. Group rows by (type, description, category-or-source).
        2. On a key collision: add to `amount`, bump `count`, keep the latest date.
        3. On first sight: create the row with count = 1.
    """
    grouped: dict[tuple, dict] = {}

    for t in transactions:
        # The LLM uses `category` for expenses and `source` for income; collapse
        # both into one value so similar rows group together regardless of type key.
        cat_or_src = t.get("category") or t.get("source")
        # The salary-plan bucket (expense rows only). Part of the key so rows tagged
        # to different buckets never merge into one — otherwise a tag would be lost.
        allocation = t.get("allocation")
        key = (t.get("type"), t.get("description"), cat_or_src, allocation)
        d = t.get("date")

        if key in grouped:
            row = grouped[key]
            row["amount"] += t.get("amount", 0)
            row["count"] += 1
            # Keep the latest date. ISO "YYYY-MM-DD" strings sort lexicographically,
            # so a plain string compare correctly finds the newer date.
            if d and (row["date"] is None or str(d) > str(row["date"])):
                row["date"] = d
        else:
            grouped[key] = {
                "type": t.get("type"),
                "amount": t.get("amount", 0),
                "category_or_source": cat_or_src,
                "description": t.get("description"),
                "date": d,
                "count": 1,
                # Carried through so the review table can prefill the Allocation
                # column with the LLM's guess; None for income / no active plan.
                "allocation": allocation,
            }

    return list(grouped.values())
