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

# @router.post("/register", response_model=UserSchema)
# async def register_user(
#     username: str = Form(...),
#     password: str = Form(...),
#     fullname: str = Form(...),
#     role: str = Form("user"),
#     file: UploadFile = File(None),
#     db: Session = Depends(get_db)
# ):
#     # Check if user exists
#     existing_user = db.query(models.User).filter(models.User.username == username).first()
#     if existing_user:
#         raise HTTPException(status_code=400, detail="Username already registered")
# 
#     new_user = models.User(
#         username=username,
#         fullname=fullname,
#         hashed_password=get_password_hash(password),
#         role=role
#     )
#     db.add(new_user)
#     db.commit()
#     db.refresh(new_user)
# 
#     # If a face photo was provided during registration, process and save it directly in S3
#     if file and file.filename:
#         contents = await file.read()
#         face_binary = await face_service.process_and_crop_binary(contents)
#         if face_binary:
#             s3_key = f"faces/user_{new_user.id}.jpg"
#             success = s3_service.upload_file(face_binary, s3_key)
#             if success:
#                 new_user.face_image = s3_key
#                 db.commit()
#                 db.refresh(new_user)
# 
#     return new_user



@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login via external IBIK User Management API.
    """
    try:
        # Authenticate with external API
        external_data = await external_auth_service.authenticate_external(
            form_data.username, 
            form_data.password
        )
        
        # external_data is expected to contain 'access_token' (or similar)
        # We use the token returned by the external API as our own, since we share SECRET_KEY.
        token = external_data.get("access_token") or external_data.get("token") or external_data.get("data", {}).get("token")
        if not token:
            raise HTTPException(status_code=502, detail="External API did not return a valid token")

        # Sync user info from body (Since it's not and actually missing in the JWT token payload)
        user_data = external_data.get("data", {}).get("user", {})
        # Use id_user as the identifier to match JWT 'sub' claim used in deps.py
        ext_id = str(user_data.get("id_user") or user_data.get("id") or form_data.username)
        fullname = user_data.get("nama_lengkap_akun") or user_data.get("fullname") or user_data.get("name") or ext_id
        
        # Defensive role extraction
        role_raw = user_data.get("role") or external_data.get("data", {}).get("role_lppm") or "user"
        role = str(role_raw).lower()

        # Force admin role for superadmin username
        if form_data.username.lower() == "superadmin":
            role = "admin"

        # Sync user to local DB immediately
        user = db.query(models.User).filter(models.User.username == ext_id).first()
        if not user:
            user = models.User(
                username=ext_id,
                fullname=fullname,
                role=role,
                hashed_password="EXTERNAL_AUTH"
            )
            db.add(user)
        else:
            user.fullname = fullname
            user.role = role
        
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            import logging
            logging.getLogger(__name__).error(f"Failed to sync user on login: {e}")
            
        return {"access_token": token, "token_type": "bearer"}
    except HTTPException as he:
        # Re-raise FastAPIs HTTPExceptions
        raise he
    except Exception as e:
        # Log and provide detail for other unexpected errors
        import logging
        logging.getLogger(__name__).error(f"Login error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected login error: {str(e)}")
