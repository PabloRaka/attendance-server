from fastapi import APIRouter, Depends, HTTPException, status, Response, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from typing import Optional, List
from app import models
from app.database import get_db
from app.api.deps import get_admin_user
from app.schemas.user import User as UserSchema, UserUpdate
from app.services import face_service
from app.utils.auth import get_password_hash

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/users", response_model=List[UserSchema])
async def admin_get_all_users(
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    users = db.query(models.User).all()
    return users


@router.get("/user/{user_id}/logs")
async def admin_get_user_logs(
    user_id: int,
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    logs = db.query(models.Attendance).filter(
        models.Attendance.user_id == user_id
    ).order_by(models.Attendance.timestamp.desc()).all()
    return logs


from datetime import datetime, timedelta

@router.get("/logs")
async def admin_get_all_logs(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Attendance, models.User.fullname, models.User.username)\
        .join(models.User, models.Attendance.user_id == models.User.id)
    
    # We assume the user is in WIB (UTC+7). 
    # To filter by local date, we need to convert the range to UTC.
    if start_date and start_date.strip():
        # Start of WIB day (00:00:00) -> UTC (Yesterday 17:00:00)
        local_start = datetime.strptime(start_date, "%Y-%m-%d")
        utc_start = local_start - timedelta(hours=7)
        query = query.filter(models.Attendance.timestamp >= utc_start)
        
    if end_date and end_date.strip():
        # End of WIB day (23:59:59) -> UTC (Today 16:59:59)
        local_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        utc_end = local_end - timedelta(hours=7)
        query = query.filter(models.Attendance.timestamp < utc_end)
        
    results = query.order_by(models.Attendance.timestamp.desc()).all()
    
    # Format output
    return [
        {
            "id": log.Attendance.id,
            "user_id": log.Attendance.user_id,
            "username": log.username,
            "fullname": log.fullname,
            "timestamp": log.Attendance.timestamp,
            "method": log.Attendance.method,
            "attendance_type": log.Attendance.attendance_type
        } for log in results
    ]


@router.delete("/user/{user_id}")
async def admin_delete_user(
    user_id: int,
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete super admin")

    db.delete(user)
    db.commit()
    return {"status": "success", "message": f"User {user.username} deleted"}


@router.get("/user/{user_id}/face")
async def admin_get_user_face(
    user_id: int,
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.face_image:
        raise HTTPException(status_code=404, detail="Face photo not found")
    return Response(content=user.face_image, media_type="image/jpeg")


@router.delete("/user/{user_id}/face")
async def admin_delete_face(
    user_id: int,
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin-only: remove a user's stored face photo from DB."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.face_image = None
    db.commit()
    return {"message": "Face photo removed"}


@router.post("/user/{user_id}/face")
async def admin_update_face(
    user_id: int,
    file: UploadFile = File(...),
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin-only: replace any user's face photo in DB."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    contents = await file.read()
    face_binary = await face_service.process_and_crop_binary(contents)
    if not face_binary:
        raise HTTPException(status_code=400, detail="Wajah tidak terdeteksi")

    user.face_image = face_binary
    db.commit()
    return {"status": "success", "message": f"Face photo for {user.username} updated"}


@router.put("/user/{user_id}")
async def admin_update_user(
    user_id: int,
    user_update: UserUpdate,
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin-only: update user details like fullname, role, and password."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.username == "admin" and user_update.role and user_update.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot downgrade super admin")

    if user_update.fullname is not None:
        user.fullname = user_update.fullname
    if user_update.role is not None:
        user.role = user_update.role
    if user_update.password is not None and user_update.password != "":
        user.hashed_password = get_password_hash(user_update.password)

    db.commit()
    return {"status": "success", "message": f"User {user.username} updated"}


@router.post("/user/{user_id}/force-attendance")
async def admin_force_attendance(
    user_id: int,
    attendance_type: str = Query(..., regex="^(in|out)$"),
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin-only: force an attendance record for a user."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_record = models.Attendance(
        user_id=user.id,
        method="admin_force",
        attendance_type=attendance_type
    )
    db.add(new_record)
    db.commit()
    return {"status": "success", "message": f"Attendance {attendance_type} forced for {user.username}"}


