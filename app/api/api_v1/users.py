from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from app import models
from app.database import get_db
from app.api.deps import get_current_user
from app.schemas.user import User as UserSchema
from app.schemas.pagination import PaginatedResponse
from app.services import face_service, s3_service
from app.utils.auth import get_password_hash, verify_password
from fastapi import Query
from fastapi.responses import RedirectResponse
import math

router = APIRouter(prefix="/api/user", tags=["Users"])

@router.get("/profile", response_model=UserSchema)
async def get_profile(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/upload-face", response_model=UserSchema)
async def upload_face(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload face photo (Async & DB-Stored)."""
    # Regular users can only upload once
    if current_user.role != "admin" and current_user.face_image:
        raise HTTPException(
            status_code=403,
            detail="Foto wajah sudah ada. Hubungi admin untuk menggantinya."
        )

    contents = await file.read()
    face_binary = await face_service.process_and_crop_binary(contents)
    if not face_binary:
        raise HTTPException(status_code=400, detail="Wajah tidak terdeteksi")

    # Save to Database directly
    current_user.face_image = face_binary
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/history", response_model=PaginatedResponse[dict])
async def get_attendance_history(
    page: int = Query(1, ge=1),
    size: int = Query(15, ge=1, le=100),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Attendance).filter(
        models.Attendance.user_id == current_user.id
    )
    
    total = query.count()
    history = query.order_by(models.Attendance.timestamp.desc())\
        .offset((page - 1) * size).limit(size).all()
    
    # We use dict for history to match previous expected format or include 
    # any extra fields if needed, or we could use an Attendance schema.
    # Since the previous code returned models objects directly, 
    # and FastAPI handles them, we'll return them as items.
    
    return {
        "items": history,
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total > 0 else 1
    }


@router.post("/change-password")
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    current_user.hashed_password = get_password_hash(new_password)
    db.commit()
    return {"message": "Password updated successfully"}


@router.get("/face-photo")
async def get_face_photo(current_user: models.User = Depends(get_current_user)):
    """Serve the user's stored face photo via S3 presigned URL."""
    if not current_user.face_image:
        raise HTTPException(status_code=404, detail="Face photo not found")
    
    return Response(content=current_user.face_image, media_type="image/jpeg")


