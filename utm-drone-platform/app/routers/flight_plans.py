from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_operator
from app.database import get_db
from app.models.drone import Drone
from app.models.flight_plan import FlightPlan, FlightPlanStatus
from app.models.operator import Operator
from app.schemas.flight_plan import FlightPlanCreate, FlightPlanOut
from app.services.flight_review_service import run_full_review

router = APIRouter(prefix="/flight-plans", tags=["Flight Plans"])


@router.post("", response_model=FlightPlanOut, status_code=201)
def create_flight_plan(
    payload: FlightPlanCreate,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    drone = db.query(Drone).filter(Drone.id == payload.drone_id, Drone.operator_id == current_operator.id).first()
    if not drone:
        raise HTTPException(status_code=404, detail="Drone not found for this operator.")

    plan = FlightPlan(
        operator_id=current_operator.id,
        drone_id=payload.drone_id,
        mission_name=payload.mission_name,
        purpose=payload.purpose,
        waypoints=[wp.model_dump() for wp in payload.waypoints],
        planned_start_time=payload.planned_start_time,
        planned_end_time=payload.planned_end_time,
        max_altitude_m=payload.max_altitude_m,
        priority=payload.priority,
        status=FlightPlanStatus.DRAFT,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/{flight_plan_id}/submit-for-review")
def submit_for_review(
    flight_plan_id: str,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    plan = (
        db.query(FlightPlan)
        .filter(FlightPlan.id == flight_plan_id, FlightPlan.operator_id == current_operator.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Flight plan not found.")

    if plan.status not in (FlightPlanStatus.DRAFT, FlightPlanStatus.CONFLICT_DETECTED, FlightPlanStatus.LAANC_DENIED):
        raise HTTPException(
            status_code=400,
            detail=f"Flight plan in status '{plan.status}' cannot be resubmitted for review.",
        )

    result = run_full_review(db, plan)
    return result


@router.post("/{flight_plan_id}/activate", response_model=FlightPlanOut)
def activate_flight_plan(
    flight_plan_id: str,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    plan = (
        db.query(FlightPlan)
        .filter(FlightPlan.id == flight_plan_id, FlightPlan.operator_id == current_operator.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Flight plan not found.")
    if plan.status != FlightPlanStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Only APPROVED flight plans can be activated.")

    plan.status = FlightPlanStatus.ACTIVE
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/{flight_plan_id}/complete", response_model=FlightPlanOut)
def complete_flight_plan(
    flight_plan_id: str,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    plan = (
        db.query(FlightPlan)
        .filter(FlightPlan.id == flight_plan_id, FlightPlan.operator_id == current_operator.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Flight plan not found.")
    if plan.status != FlightPlanStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Only ACTIVE flight plans can be completed.")

    plan.status = FlightPlanStatus.COMPLETED
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/{flight_plan_id}/cancel", response_model=FlightPlanOut)
def cancel_flight_plan(
    flight_plan_id: str,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    plan = (
        db.query(FlightPlan)
        .filter(FlightPlan.id == flight_plan_id, FlightPlan.operator_id == current_operator.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Flight plan not found.")
    if plan.status in (FlightPlanStatus.COMPLETED, FlightPlanStatus.ABORTED, FlightPlanStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Flight plan already in terminal status '{plan.status}'.")

    plan.status = FlightPlanStatus.CANCELLED
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("", response_model=List[FlightPlanOut])
def list_my_flight_plans(
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    return db.query(FlightPlan).filter(FlightPlan.operator_id == current_operator.id).all()


@router.get("/{flight_plan_id}", response_model=FlightPlanOut)
def get_flight_plan(
    flight_plan_id: str,
    db: Session = Depends(get_db),
    current_operator: Operator = Depends(get_current_operator),
):
    plan = (
        db.query(FlightPlan)
        .filter(FlightPlan.id == flight_plan_id, FlightPlan.operator_id == current_operator.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Flight plan not found.")
    return plan


@router.get("/active/all", response_model=List[FlightPlanOut])
def list_all_active_flight_plans(db: Session = Depends(get_db)):
    """
    Airspace-wide view of currently active operations — used by the
    dashboard's live map. Not scoped to one operator since safe
    deconfliction requires visibility across all traffic.
    """
    return db.query(FlightPlan).filter(FlightPlan.status == FlightPlanStatus.ACTIVE).all()
