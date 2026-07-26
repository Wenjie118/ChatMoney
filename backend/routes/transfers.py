"""
Transfer endpoints — internal money movements between wallets.

    POST  /transfers        create (BOTH wallets REQUIRED on this manual path)
    PATCH /transfers/{id}    fill in previously-NULL wallet sides (imported rows)

A transfer is neither income nor expense: it nets to zero across the system.
The manual path requires both wallets (enforced by the required int fields on
TransferCreate); db.create_transfer additionally rejects amount ≤ 0 and equal
wallets, surfaced here as 422.
"""

from fastapi import APIRouter, HTTPException

from db import create_transfer, update_transfer_wallets, DatabaseConnectionError
from schemas.models import TransferCreate, TransferPatch, TransferResponse

router = APIRouter()


@router.post("", response_model=TransferResponse)
def create(payload: TransferCreate) -> TransferResponse:
    """Create a wallet-to-wallet transfer. Both wallets are required (missing =
    422 from Pydantic); equal wallets or amount ≤ 0 also 422 (db ValueError)."""
    try:
        row = create_transfer(
            from_wallet=payload.from_wallet,
            to_wallet=payload.to_wallet,
            amount=payload.amount,
            description=payload.description,
            transfer_date=payload.date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TransferResponse(**row)


@router.patch("/{transfer_id}", response_model=dict)
def patch(transfer_id: int, payload: TransferPatch) -> dict:
    """Fill in previously-NULL wallet sides of an imported transfer."""
    try:
        update_transfer_wallets(transfer_id, payload.from_wallet, payload.to_wallet)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "updated", "id": transfer_id}
