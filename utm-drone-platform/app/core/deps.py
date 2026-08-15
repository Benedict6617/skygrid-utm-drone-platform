from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.operator import Operator

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_operator(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Operator:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    operator_id = decode_access_token(token)
    if operator_id is None:
        raise credentials_exception

    operator = db.query(Operator).filter(Operator.id == operator_id).first()
    if operator is None or not operator.is_active:
        raise credentials_exception

    return operator
