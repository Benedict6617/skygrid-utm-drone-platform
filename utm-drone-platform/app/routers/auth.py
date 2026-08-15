from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.operator import Operator
from app.schemas.operator import LoginRequest, OperatorCreate, OperatorOut, Token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=OperatorOut, status_code=status.HTTP_201_CREATED)
def register_operator(payload: OperatorCreate, db: Session = Depends(get_db)):
    existing = db.query(Operator).filter(Operator.contact_email == payload.contact_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An operator with this email already exists.")

    operator = Operator(
        company_name=payload.company_name,
        contact_email=payload.contact_email,
        hashed_password=hash_password(payload.password),
        faa_certificate_number=payload.faa_certificate_number,
        phone_number=payload.phone_number,
    )
    db.add(operator)
    db.commit()
    db.refresh(operator)
    return operator


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    operator = db.query(Operator).filter(Operator.contact_email == payload.contact_email).first()
    if not operator or not verify_password(payload.password, operator.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not operator.is_active:
        raise HTTPException(status_code=403, detail="This operator account is deactivated.")

    token = create_access_token(subject=operator.id)
    return Token(access_token=token)
