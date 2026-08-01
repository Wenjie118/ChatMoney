"""
Wallet endpoints — the virtual sub-wallet system.

    GET    /wallets              list active wallets with COMPUTED balances
    POST   /wallets              create a wallet
    PATCH  /wallets/{id}         rename
    DELETE /wallets/{id}         soft-delete (deactivate)
    GET    /wallets/unassigned   total (incl. baseline) + resolvable NULL rows
    GET    /wallets/{id}/ledger  movement history for the detail view

Thin routes, mirroring routes/balance.py: call db → map DatabaseConnectionError
to 503 (and ValueError to 422) → return a typed response. All balance math lives
in db.py; nothing here computes a number.
"""

from fastapi import APIRouter, HTTPException

from db import (
    create_wallet,
    get_wallets,
    get_all_wallet_balances,
    get_wallet_balance,
    set_wallet_balance,
    rename_wallet,
    deactivate_wallet,
    get_wallet_ledger,
    get_unassigned_total,
    get_unassigned_rows,
    DatabaseConnectionError,
)
from schemas.models import (
    WalletCreate,
    WalletRename,
    WalletResponse,
    LedgerEntry,
    UnassignedResponse,
    UnassignedRow,
    SetWalletBalanceRequest,
)

router = APIRouter()


@router.get("", response_model=list[WalletResponse])
def list_wallets() -> list[WalletResponse]:
    """Active wallets, each with its computed balance (batched — no N+1)."""
    try:
        rows = get_all_wallet_balances()
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [WalletResponse(**r) for r in rows]


@router.post("", response_model=WalletResponse)
def create(payload: WalletCreate) -> WalletResponse:
    """Create a wallet (starts at balance 0)."""
    try:
        wallet = create_wallet(payload.name.strip())
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return WalletResponse(id=wallet["id"], name=wallet["name"], balance=0.0)


# NOTE: this literal path is declared BEFORE the "/{wallet_id}/ledger" route so
# "unassigned" is never captured as a wallet id.
@router.get("/unassigned", response_model=UnassignedResponse)
def unassigned() -> UnassignedResponse:
    """The Unassigned bucket: total money not in any active wallet (NULL-wallet
    rows + soft-deleted wallets + the pre-wallet baseline), plus the resolvable
    income/expense rows."""
    try:
        total = get_unassigned_total()
        rows = get_unassigned_rows()
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return UnassignedResponse(total=total, rows=[UnassignedRow(**r) for r in rows])


@router.patch("/{wallet_id}", response_model=WalletResponse)
def rename(wallet_id: int, payload: WalletRename) -> WalletResponse:
    """Rename a wallet; returns it with its current computed balance."""
    try:
        rename_wallet(wallet_id, payload.name.strip())
        balance = get_wallet_balance(wallet_id)
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return WalletResponse(id=wallet_id, name=payload.name.strip(), balance=balance)


@router.delete("/{wallet_id}")
def delete(wallet_id: int) -> dict:
    """Soft-delete a wallet (its money folds into Unassigned)."""
    try:
        deactivate_wallet(wallet_id)
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "deactivated", "id": wallet_id}


@router.patch("/{wallet_id}/balance", response_model=WalletResponse)
def set_balance(wallet_id: int, payload: SetWalletBalanceRequest) -> WalletResponse:
    """Correct a wallet to an exact balance (records an adjustment for the delta).

    "This wallet should have this much" — changes the wallet and the overall
    balance. To move money between wallets, use a transfer instead.

    The delta is written to `wallet_adjustments`, so it never shows up as income or
    spending in the monthly summary, the charts or the AI advisor.
    """
    try:
        set_wallet_balance(wallet_id, payload.amount)
        balance = get_wallet_balance(wallet_id)
        wallet = next((w for w in get_wallets(active_only=False) if w["id"] == wallet_id), None)
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found.")
    return WalletResponse(id=wallet_id, name=wallet["name"], balance=balance)


@router.get("/{wallet_id}/ledger", response_model=list[LedgerEntry])
def ledger(wallet_id: int) -> list[LedgerEntry]:
    """Chronological movements affecting the wallet (sums to its balance)."""
    try:
        entries = get_wallet_ledger(wallet_id)
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [LedgerEntry(**e) for e in entries]
