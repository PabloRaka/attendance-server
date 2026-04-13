from fastapi import APIRouter, Depends, HTTPException, status, Response, Query, UploadFile, File
from fastapi.responses import StreamingResponse, RedirectResponse
import io
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from typing import Optional, List
from app import models
from app.database import get_db
from app.api.deps import get_admin_user
from app.schemas.user import User as UserSchema, UserUpdate
from app.schemas.pagination import PaginatedResponse
from app.services import face_service, s3_service
from app.utils.auth import get_password_hash
from sqlalchemy import or_
import math

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/users", response_model=PaginatedResponse[UserSchema])
async def admin_get_all_users(
    page: int = Query(1, ge=1),
    size: int = Query(15, ge=1, le=100),
    search: Optional[str] = Query(None),
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.User)
    
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(or_(
            models.User.fullname.ilike(search_term),
            models.User.username.ilike(search_term)
        ))
    
    total = query.count()
    users = query.offset((page - 1) * size).limit(size).all()
    
    return {
        "items": users,
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total > 0 else 1
    }


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


from datetime import datetime, timedelta, timezone

@router.get("/logs")
async def admin_get_all_logs(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(15, ge=1, le=100),
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Attendance, models.User.fullname, models.User.username)\
        .join(models.User, models.Attendance.user_id == models.User.id)
    
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(or_(
            models.User.fullname.ilike(search_term),
            models.User.username.ilike(search_term)
        ))

    # We assume the user is in WIB (UTC+7). 
    if start_date and start_date.strip():
        local_start = datetime.strptime(start_date, "%Y-%m-%d")
        utc_start = local_start - timedelta(hours=7)
        query = query.filter(models.Attendance.timestamp >= utc_start)
        
    if end_date and end_date.strip():
        local_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        utc_end = local_end - timedelta(hours=7)
        query = query.filter(models.Attendance.timestamp < utc_end)
        
    total = query.count()
    results = query.order_by(models.Attendance.timestamp.desc())\
        .offset((page - 1) * size).limit(size).all()
    
    # Format output
    items = [
        {
            "id": log.Attendance.id,
            "user_id": log.Attendance.user_id,
            "username": log.username,
            "fullname": log.fullname,
            "timestamp": log.Attendance.timestamp,
            "method": log.Attendance.method,
            "attendance_type": log.Attendance.attendance_type,
            "status": log.Attendance.status,
            "latitude": log.Attendance.latitude,
            "longitude": log.Attendance.longitude,
            "location_name": log.Attendance.location_name
        } for log in results
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total > 0 else 1
    }


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

    # Save binary directly to DB
    user.face_image = face_binary
    db.commit()
    db.refresh(user)
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

    # Status logic for 'in' type
    status = None
    if attendance_type == "in":
        # Get current time in WIB (UTC+7)
        wib_timezone = timezone(timedelta(hours=7))
        now_wib = datetime.now(wib_timezone)
        
        # Check if past 08:15
        if now_wib.hour > 8 or (now_wib.hour == 8 and now_wib.minute > 15):
            status = "terlambat"
        else:
            status = "tepat waktu"

    new_record = models.Attendance(
        user_id=user.id,
        method="admin_force",
        attendance_type=attendance_type,
        status=status
    )
    db.add(new_record)
    db.commit()
    return {"status": "success", "message": f"Attendance {attendance_type} forced for {user.username}"}


@router.get("/export-excel")
async def admin_export_excel(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin-only: Export attendance logs to an Excel file with date and search filtering."""
    query = db.query(models.Attendance, models.User.fullname, models.User.username)\
        .join(models.User, models.Attendance.user_id == models.User.id)
    
    if search and search.strip():
        search_term = f"%{search.strip()}%"
        from sqlalchemy import or_
        query = query.filter(or_(
            models.User.fullname.ilike(search_term),
            models.User.username.ilike(search_term)
        ))
    
    if start_date and start_date.strip():
        local_start = datetime.strptime(start_date, "%Y-%m-%d")
        utc_start = local_start - timedelta(hours=7)
        query = query.filter(models.Attendance.timestamp >= utc_start)
        
    if end_date and end_date.strip():
        local_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        utc_end = local_end - timedelta(hours=7)
        query = query.filter(models.Attendance.timestamp < utc_end)
        
    results = query.order_by(models.Attendance.timestamp.desc()).all()

    # Create Excel Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Rekap Absensi"

    # Header
    headers = ["No", "Nama Lengkap", "Username", "Tanggal", "Jam (WIB)", "Tipe", "Status", "Metode", "Lokasi"]
    ws.append(headers)
    
    # Header Styling
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Data Rows
    for i, res in enumerate(results, start=1):
        # res.Attendance.timestamp is UTC
        # Convert to local WIB for display
        local_time = res.Attendance.timestamp + timedelta(hours=7)
        
        row = [
            i,
            res.fullname,
            res.username,
            local_time.strftime("%d-%m-%Y"),
            local_time.strftime("%H:%M"),
            "Masuk" if res.Attendance.attendance_type == "in" else "Keluar",
            res.Attendance.status or "-",
            res.Attendance.method.replace("_", " ").title() if res.Attendance.method else "-",
            res.Attendance.location_name or (f"{res.Attendance.latitude}, {res.Attendance.longitude}" if res.Attendance.latitude else "-")
        ]
        ws.append(row)

    # Auto-adjust column widths
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = adjusted_width

    # Save to memory buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"rekap_absensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


from app.tasks import perform_auto_checkout

@router.post("/trigger-auto-checkout")
async def admin_trigger_auto_checkout(
    admin: models.User = Depends(get_admin_user)
):
    """Admin-only: Manually trigger the 23:00 WIB auto check-out logic for testing."""
    count = await perform_auto_checkout()
    return {"status": "success", "message": f"Auto check-out processed for {count} users"}


