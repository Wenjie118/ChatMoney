"""
HTTP route modules.

Each file here defines an `APIRouter` instance named `router` and attaches
endpoints to it with decorators (@router.get, @router.post, ...). main.py imports
each `router` and mounts it under a URL prefix:

    routes/balance.py       -> mounted at /balance
    routes/transactions.py  -> mounted at /transactions
    routes/advisor.py       -> mounted at /advisor
"""
