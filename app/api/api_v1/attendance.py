from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
import cv2
import numpy as np
import secrets
from datetime import datetime, date, timedelta, timezone
from pyzbar.pyzbar import decode
from sqlalchemy import func as sql_func

from app import models
from app.database import get_db
from app.api.deps import get_current_user, get_admin_user
from app.services import face_service, s3_service, location_service
from app.core.config import settings

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])

async def record_attendance(db: Session, user_id: int, method: str, latitude: str = None, longitude: str = None):
    location_name = None
    if latitude and longitude:
        location_name = await location_service.get_address_from_coords(latitude, longitude)

    today = date.today()
    # Find last attendance for today
    last_attendance = db.query(models.Attendance).filter(
        models.Attendance.user_id == user_id,
        sql_func.date(models.Attendance.timestamp) == today
    ).order_by(models.Attendance.timestamp.desc()).first()

    # Toggle logic: if none today or last was 'out', then 'in'. Else 'out'.
    new_type = "in"
    if last_attendance and last_attendance.attendance_type == "in":
        new_type = "out"

    # Status logic for 'in' type
    status = None
    if new_type == "in":
        # Get current time in WIB (UTC+7)
        wib_timezone = timezone(timedelta(hours=7))
        now_wib = datetime.now(wib_timezone)
        
        # Check if past 08:15
        if now_wib.hour > 8 or (now_wib.hour == 8 and now_wib.minute > 15):
            status = "terlambat"
        else:
            status = "tepat waktu"

    new_record = models.Attendance(
        user_id=user_id,
        method=method,
        attendance_type=new_type,
        status=status,
        latitude=latitude,
        longitude=longitude,
        location_name=location_name
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return new_record


@router.post("/qr")
async def attendance_qr(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Legacy endpoint for web scanning user's QR."""
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    decoded_objs = decode(image)
    if not decoded_objs:
        raise HTTPException(status_code=400, detail="No QR code detected")

    qr_data = decoded_objs[0].data.decode("utf-8")
    
    user = db.query(models.User).filter(models.User.username == qr_data).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {qr_data} not found")

    record = await record_attendance(db, user.id, "qr_scan")
    return {"status": "success", "user": user.fullname, "type": record.attendance_type, "time": record.timestamp, "attendance_status": record.status}


@router.get("/token")
async def generate_token(admin: models.User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Generates a dynamic token for the web dashboard to display."""
    token = secrets.token_urlsafe(32)
    # Expire in 60 seconds (generous for network lag)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
    
    new_challenge = models.QRChallenge(
        token=token,
        expires_at=expires_at
    )
    db.add(new_challenge)
    db.commit()
    return {"token": token, "expires_in": 60}


@router.post("/verify-token")
async def verify_token(
    token: str = Form(...), 
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Verifies a token scanned by the mobile user and records attendance."""
    challenge = db.query(models.QRChallenge).filter(
        models.QRChallenge.token == token,
        models.QRChallenge.expires_at > datetime.now(timezone.utc)
    ).first()

    if not challenge:
        raise HTTPException(status_code=400, detail="Invalid or expired QR code")

    # Record attendance for the user who IS SCANNING
    record = await record_attendance(db, current_user.id, "mobile_scan")
    
    # Optional: Delete or mark challenge as used
    db.delete(challenge)
    db.commit()

    return {
        "status": "success", 
        "user": current_user.fullname, 
        "type": record.attendance_type, 
        "time": record.timestamp,
        "attendance_status": record.status
    }


@router.post("/face")
async def attendance_face(
    file: UploadFile = File(...),
    latitude: str = Form(None),
    longitude: str = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Attendance via face recognition (Async & DB-Stored).
    """
    if not current_user.face_image:
        raise HTTPException(
            status_code=400,
            detail="Foto wajah belum diupload. Silakan upload foto wajah di halaman Profile terlebih dahulu."
        )

    contents = await file.read()
    try:
        # Comparison using binary data directly from DB
        similarity = await face_service.async_compare_faces(current_user.face_image, contents)
    except face_service.LivenessError as e:
        raise HTTPException(
            status_code=403,
            detail=str(e)
        )

    if similarity < settings.FACE_SIMILARITY_THRESHOLD:
        raise HTTPException(
            status_code=403,
            detail=f"Wajah tidak cocok (similarity: {similarity:.0%}). Dibutuhkan minimal {settings.FACE_SIMILARITY_THRESHOLD:.0%}. Pastikan pencahayaan baik."
        )

    record = await record_attendance(db, current_user.id, "face_recognition", latitude, longitude)
    return {
        "status": "success",
        "user": current_user.fullname,
        "type": record.attendance_type,
        "time": record.timestamp,
        "similarity": round(similarity, 3),
        "attendance_status": record.status
    }
