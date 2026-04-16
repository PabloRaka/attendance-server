from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.utils.auth import get_password_hash, verify_password, create_access_token
from app.schemas.user import UserCreate, User as UserSchema, Token
from app.services import face_service, s3_service
from app.services.external_auth_service import external_auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def resolve_external_username(user_data: dict, fallback_username: str) -> str:
    return str(
        user_data.get("username_akun")
        or user_data.get("npm_akun")
        or user_data.get("username")
        or user_data.get("npm")
        or fallback_username
    )


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login via external IBIK User Management API, with local fallback for admin-created users.
    """
    external_data = None
    try:
        # 1. Attempt External Authentication first
        external_data = await external_auth_service.authenticate_external(
            form_data.username, 
            form_data.password
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).info(f"External auth failed for {form_data.username}, trying local fallback: {e}")

    # 2. Process external authentication result if successful
    if external_data:
        try:
            # external_data is expected to contain 'access_token' (or similar)
            token = external_data.get("access_token") or external_data.get("token") or external_data.get("data", {}).get("token")
            if not token:
                raise HTTPException(status_code=502, detail="External API did not return a valid token")

            # Sync user info
            user_data = external_data.get("data", {}).get("user", {})
            ext_id = str(user_data.get("id_user") or user_data.get("id") or form_data.username)
            external_username = resolve_external_username(user_data, form_data.username)
            fullname = user_data.get("nama_lengkap_akun") or user_data.get("fullname") or user_data.get("name") or ext_id
            
            # Defensive role extraction
            role_raw = user_data.get("role") or external_data.get("data", {}).get("role_lppm") or "user"
            role = str(role_raw).lower()

            if form_data.username.lower() == "superadmin":
                role = "admin"

            # Sync user to local DB
            user = db.query(models.User).filter(models.User.external_auth_id == ext_id).first()
            if not user:
                user = db.query(models.User).filter(models.User.username == ext_id).first()
            if not user:
                user = db.query(models.User).filter(models.User.username == external_username).first()
            
            if not user:
                user = models.User(
                    username=external_username,
                    external_auth_id=ext_id,
                    fullname=fullname,
                    role=role,
                    hashed_password="EXTERNAL_AUTH"
                )
                db.add(user)
            else:
                user.username = external_username
                user.external_auth_id = ext_id
                user.fullname = fullname
            
            db.commit()
            return {"access_token": token, "token_type": "bearer"}
        except HTTPException as he:
            raise he
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error syncing external user: {e}")
            # Fall through to local auth if sync fails? No, if external auth suceeded but sync failed, it's a server error.
            raise HTTPException(status_code=500, detail="Gagal menyinkronkan data user")

    # 3. Local Fallback Authentication
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if user and user.hashed_password != "EXTERNAL_AUTH" and verify_password(form_data.password, user.hashed_password):
        # Create a local token compatible with deps.py:get_current_user
        access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
        return {"access_token": access_token, "token_type": "bearer"}

    # 4. Final Failure
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Username atau password salah",
        headers={"WWW-Authenticate": "Bearer"},
    )
