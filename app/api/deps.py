from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..core.config import settings
from ..schemas.user import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def resolve_token_username(payload: dict) -> str | None:
    data_obj = payload.get("data", {})
    return (
        payload.get("username_akun")
        or data_obj.get("username_akun")
        or payload.get("npm_akun")
        or data_obj.get("npm_akun")
        or payload.get("username")
        or payload.get("npm")
    )

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = resolve_token_username(payload)
        external_auth_id = str(payload.get("sub")) if payload.get("sub") is not None else None

        if username is None and external_auth_id is None:
            raise credentials_exception
            
        # Get extra info if available in token for JIT provisioning
        # Support various name keys commonly used in different systems/APIs
        data_obj = payload.get("data", {})
        fullname_from_token = (
            payload.get("nama_lengkap_akun") or
            data_obj.get("nama_lengkap_akun") or
            payload.get("nama_lengkap") or
            data_obj.get("nama_lengkap") or
            payload.get("name") or 
            payload.get("fullname") or 
            payload.get("full_name") or 
            payload.get("nama") or 
            data_obj.get("nama")
        )
        # Fallback to username only if NO name found in token
        fullname = fullname_from_token or username

        role = payload.get("role") or "user"
        
        # Force admin role for superadmin accounts to avoid JIT downgrade
        if username and username.lower() in ["superadmin", "1"]:
            role = "admin"

        
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = None
    if external_auth_id is not None:
        user = db.query(User).filter(User.external_auth_id == external_auth_id).first()

    if not user and token_data.username is not None:
        user = db.query(User).filter(User.username == token_data.username).first()
    
    # JIT Provisioning & Sync: if user exists, sync name/role. If not exists, create.
    if user:
        # Sync existing user data ONLY if a real name was found in the token
        # This prevents overwriting a correct name (synced during login) with a fallback ID.
        changed = False
        if fullname_from_token and user.fullname != fullname_from_token:
            user.fullname = fullname_from_token
            changed = True
        if changed:
            try:
                db.commit()
                db.refresh(user)
            except Exception as e:
                db.rollback()
                # We can log this, but maybe not fail the whole request just because sync failed
                import logging
                logging.getLogger(__name__).error(f"Failed to sync user data: {e}")
    else:
        # Create new user (JIT Provisioning)
        user = User(
            username=token_data.username or external_auth_id,
            external_auth_id=external_auth_id,
            fullname=fullname,
            role=role,
            hashed_password="EXTERNAL_AUTH" # Local password not needed
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to synchronize user data: {e}")
            
    return user

def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user
