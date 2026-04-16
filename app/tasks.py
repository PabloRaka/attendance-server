import asyncio
import logging
from datetime import datetime, date, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from .database import SessionLocal
from . import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AUTO_CHECKOUT_LOCK_KEY = 2300
WIB_TIMEZONE = timezone(timedelta(hours=7))


def _get_wib_today() -> date:
    return datetime.now(WIB_TIMEZONE).date()


def _try_acquire_auto_checkout_lock(db: Session) -> bool:
    bind = db.get_bind()
    dialect = bind.dialect.name if bind else ""

    if dialect.startswith("postgresql"):
        return bool(
            db.execute(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": AUTO_CHECKOUT_LOCK_KEY},
            ).scalar()
        )

    return True


def _release_auto_checkout_lock(db: Session) -> None:
    bind = db.get_bind()
    dialect = bind.dialect.name if bind else ""

    if dialect.startswith("postgresql"):
        db.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": AUTO_CHECKOUT_LOCK_KEY},
        )


def _has_checkout_for_date(db: Session, user_id: int, target_date: date) -> bool:
    return (
        db.query(models.Attendance.id)
        .filter(
            models.Attendance.user_id == user_id,
            func.date(models.Attendance.timestamp) == target_date,
            models.Attendance.attendance_type == "out",
        )
        .first()
        is not None
    )

async def perform_auto_checkout():
    """
    Finds all users who checked in today but haven't checked out,
    and records an automatic 'out' attendance for them.
    """
    db = SessionLocal()
    try:
        if not _try_acquire_auto_checkout_lock(db):
            logger.info("Auto check-out skipped because another process holds the scheduler lock.")
            return 0

        today = _get_wib_today()
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
            
            # 3. Only create one automatic check-out per user per day.
            if (
                last_record
                and last_record.attendance_type == "in"
                and not _has_checkout_for_date(db, user_id, today)
            ):
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
        try:
            _release_auto_checkout_lock(db)
        except Exception as lock_error:
            logger.warning(f"Failed to release auto check-out lock: {lock_error}")
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
            now_wib = datetime.now(WIB_TIMEZONE)
            
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
