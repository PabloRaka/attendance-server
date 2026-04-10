import asyncio
import logging
from datetime import datetime, date, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from .database import SessionLocal
from . import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def perform_auto_checkout():
    """
    Finds all users who checked in today but haven't checked out,
    and records an automatic 'out' attendance for them.
    """
    db = SessionLocal()
    try:
        today = date.today()
        logger.info(f"Starting auto check-out for date: {today}")
        
        # 1. Get all user IDs
        users = db.query(models.User.id).all()
        user_ids = [u.id for u in users]
        
        count = 0
        for user_id in user_ids:
            # 2. Get latest attendance for this user today
            last_record = db.query(models.Attendance).filter(
                models.Attendance.user_id == user_id,
                func.date(models.Attendance.timestamp) == today
            ).order_by(models.Attendance.timestamp.desc()).first()
            
            # 3. If latest is 'in', then auto-checkout
            if last_record and last_record.attendance_type == "in":
                new_record = models.Attendance(
                    user_id=user_id,
                    method="system_auto",
                    attendance_type="out",
                    status="auto"
                )
                db.add(new_record)
                count += 1
        
        db.commit()
        logger.info(f"Auto check-out complete. {count} users processed.")
        return count
    except Exception as e:
        logger.error(f"Error during auto check-out: {e}")
        db.rollback()
        return 0
    finally:
        db.close()

async def scheduler_loop():
    """
    A background loop that checks every minute.
    Triggers 'perform_auto_checkout' at exactly 23:00 WIB.
    """
    logger.info("Background scheduler started (Waiting for 23:00 WIB)...")
    while True:
        try:
            # Get current time in WIB (UTC+7)
            wib_timezone = timezone(timedelta(hours=7))
            now_wib = datetime.now(wib_timezone)
            
            # Check if it's 23:00 (11 PM)
            if now_wib.hour == 23 and now_wib.minute == 0:
                logger.info("Triggering 23:00 WIB Auto Check-out...")
                await perform_auto_checkout()
                # Sleep for 61 seconds to ensure we don't trigger twice in the same minute
                await asyncio.sleep(61)
            else:
                # Check every 30 seconds to be precise but not too frequent
                await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
            await asyncio.sleep(60)
