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

from typing import Any


def consolidate_transactions(transactions: list[dict]) -> list[dict]:
    """Merge identical transactions and sum their amounts.

    Args:
        transactions: raw dicts from `llm.parse_pdf_transactions`, each shaped like
            {type, amount, category|source, description, date}.

    Returns:
        A list of consolidated dicts. Decide the exact output shape you want the
        frontend table to consume (e.g. include a "count" field).

    TODO: port the grouping logic from the old app.py `consolidate_transactions`:
        1. Build a dict keyed by (type, description, category-or-source).
        2. On a key collision: add to `amount`, increment a count, keep latest date.
        3. On first sight: create the row with count = 1.
        4. Return list(grouped.values()).
    """
    # TODO: implement (see steps above)
    raise NotImplementedError("Port consolidate_transactions from the old app.py")
