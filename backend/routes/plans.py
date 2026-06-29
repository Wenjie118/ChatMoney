"""
Salary allocation plan endpoints.

    GET  /plans          -> the active plan (+ buckets), or null when none exists
    PUT  /plans          -> save the whole draft (create-or-update + validation)
    GET  /plans/actuals  -> deterministic planned-vs-actual table for a month

Follows the routes/balance.py reference pattern: call into the existing db.py
functions, then translate domain errors into HTTP errors
(DatabaseConnectionError -> 503, ValueError -> 422).

ARCHITECTURE: all the planned-vs-actual math + the balancing rule (Savings =
salary - sum(non-Savings targets)) live in Python — here and in db.py — never in
the LLM. PUT /plans is the SERVER-AUTHORITATIVE save: it enforces every
validation rule from the brief regardless of what the UI shows.
"""

from datetime import date

from fastapi import APIRouter, HTTPException

from db import (
    get_active_plan,
    create_plan,
    update_plan_salary,
    add_allocation,
    update_allocation,
    deactivate_allocation,
    set_savings_target,
    get_allocation_actuals,
    DatabaseConnectionError,
)
from schemas.models import (
    PlanResponse,
    PlanSaveRequest,
    AllocationModel,
    AllocationActual,
)

router = APIRouter()


def _to_plan_response(plan: dict | None) -> PlanResponse | None:
    """Shape db.get_active_plan()'s dict into a PlanResponse. Returns None
    (-> JSON null) when there's no plan.

    `percent` passes through the STORED share (None = RM-based); the frontend
    derives the display % from the current salary draft itself.
    """
    if plan is None:
        return None

    salary = plan["salary"]
    allocations = [
        AllocationModel(
            id=a["id"],
            label=a["label"],
            target_rm=a["target_rm"],
            tracking_mode=a["tracking_mode"],
            is_default=a["is_default"],
            is_active=a["is_active"],
            # .get() so it still works before the `percent` column migration is
            # applied (older rows simply have no key -> None = RM-based).
            percent=a.get("percent"),
        )
        for a in plan["allocations"]
    ]
    return PlanResponse(id=plan["id"], salary=salary, allocations=allocations)


@router.get("", response_model=PlanResponse | None)
def read_plan() -> PlanResponse | None:
    """Return the active plan, or null when none exists yet.

    The app is fully usable with no plan — the frontend renders an empty draft the
    user can build and Save (which creates the plan via PUT /plans).
    """
    try:
        plan = get_active_plan()
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _to_plan_response(plan)


@router.put("", response_model=PlanResponse)
def save_plan(payload: PlanSaveRequest) -> PlanResponse:
    """Save the whole plan draft, enforcing the brief's validation + balancing rule.

    SAVE FLOW (server-authoritative):
      1. Validate salary S > 0.
      2. T = sum of all NON-Savings bucket targets (from the draft).
      3. If T > S: block with 422 (nothing is written).
      4. If no active plan: create one (seeds the two default buckets).
      5. Update the salary.
      6. Reconcile buckets: update existing, add new, deactivate removed
         (defaults are protected by the db guard).
      7. Savings target = S - T (the balancing bucket; never hand-entered).
      8. Return the refreshed plan.
    """
    S = payload.salary
    if S <= 0:
        raise HTTPException(status_code=422, detail="Salary must be greater than 0.")

    # Effective RM per bucket: %-based buckets derive RM from salary (server is
    # authoritative, so a stale target_rm from the client is overridden), RM-based
    # buckets use their entered target. This is what makes a salary change flow
    # correctly into EPF/SOCSO at the next save.
    def _effective_rm(b) -> float:
        if b.percent is not None:
            return round(S * b.percent / 100, 2)
        return b.target_rm

    T = sum(_effective_rm(b) for b in payload.buckets)
    if T > S:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Your allocations exceed your salary by RM{T - S:.2f}. "
                "Reduce a bucket before saving."
            ),
        )

    try:
        plan = get_active_plan()
        if plan is None:
            plan_id = create_plan(S)
            plan = get_active_plan()  # now has the two seeded defaults
        else:
            plan_id = plan["id"]

        update_plan_salary(plan_id, S)

        # Index the current NON-Savings (tagged) buckets so we can reconcile the
        # draft against them. Savings is leftover and handled separately below.
        tagged = [a for a in plan["allocations"] if a["tracking_mode"] != "leftover"]
        existing_by_id = {a["id"]: a for a in tagged}
        existing_by_label = {a["label"]: a for a in tagged}
        seen_ids: set[int] = set()

        for b in payload.buckets:
            # Match by id first; fall back to label so a freshly-seeded default
            # (e.g. "Daily Spending", which the draft sends without an id when the
            # plan was just created) updates that row instead of duplicating it.
            match = existing_by_id.get(b.id) if b.id is not None else None
            if match is None:
                match = existing_by_label.get(b.label)

            rm = _effective_rm(b)  # stored RM is always the effective RM
            if match is not None:
                update_allocation(match["id"], rm, percent=b.percent)
                seen_ids.add(match["id"])
            else:
                new_row = add_allocation(plan_id, b.label, rm, percent=b.percent)
                seen_ids.add(new_row["id"])

        # Soft-delete buckets dropped from the draft — never defaults (the db
        # guard also enforces this).
        for aid, a in existing_by_id.items():
            if aid not in seen_ids and not a["is_default"]:
                deactivate_allocation(aid)

        # Balancing rule: Savings absorbs whatever salary is left over.
        set_savings_target(plan_id, S - T)

        refreshed = get_active_plan()
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _to_plan_response(refreshed)


@router.get("/actuals", response_model=list[AllocationActual])
def plan_actuals(year: int | None = None, month: int | None = None) -> list[AllocationActual]:
    """Deterministic planned-vs-actual table for a month (defaults to current).

    Returns [] when there's no active plan. This is the SAME data fed to the
    advisor — the adherence table in the UI just renders it visually.
    """
    today = date.today()
    year = year or today.year
    month = month or today.month

    try:
        rows = get_allocation_actuals(year, month)
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return [AllocationActual(**r) for r in rows]
