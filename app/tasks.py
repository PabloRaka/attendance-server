import asyncio
import logging
from datetime import datetime, date, timedelta, timezone
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, text
from .database import SessionLocal
from .core.config import settings
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
    Finds all users whose latest attendance record is 'in', 
    meaning they haven't checked out yet.
    Records an automatic 'out' attendance for them at 23:00 WIB of their check-in day.
    """
    db = SessionLocal()
    try:
        if not _try_acquire_auto_checkout_lock(db):
            logger.info("Auto check-out skipped because another process holds the scheduler lock.")
            return 0

        now_wib = datetime.now(WIB_TIMEZONE)
        today_wib = now_wib.date()
        target_hour = settings.AUTO_CHECKOUT_HOUR
        target_minute = settings.AUTO_CHECKOUT_MINUTE

        logger.info(f"Checking for auto check-out candidates. Current WIB: {now_wib}. Target Time: {target_hour:02d}:{target_minute:02d}")
        
        bind = db.get_bind()
        dialect = bind.dialect.name if bind else ""

        # 1. Find all "dangling" IN records using a robust NOT EXISTS query
        # A dangling IN is an 'in' record that has no corresponding 'out' record on the same date (WIB).
        AttendanceOut = aliased(models.Attendance)

        if dialect.startswith("postgresql"):
            date_expr_in = func.date(func.timezone('Asia/Jakarta', models.Attendance.timestamp))
            date_expr_out = func.date(func.timezone('Asia/Jakarta', AttendanceOut.timestamp))
        else:
            date_expr_in = func.date(models.Attendance.timestamp)
            date_expr_out = func.date(AttendanceOut.timestamp)

        subquery_out = db.query(AttendanceOut.id).filter(
            AttendanceOut.user_id == models.Attendance.user_id,
            AttendanceOut.attendance_type == "out",
            date_expr_out == date_expr_in
        ).exists()

        dangling_ins = db.query(models.Attendance).filter(
            models.Attendance.attendance_type == "in",
            ~subquery_out
        ).all()

        count = 0
        for record in dangling_ins:
            # Convert record timestamp to WIB to see what date it belongs to
            record_wib = record.timestamp.astimezone(WIB_TIMEZONE)
            record_date = record_wib.date()

            # Rule for auto-checkout:
            # - If the check-in is from a past date (record_date < today_wib)
            # - OR if the check-in is from today but it's now past the configured time
            is_past_day = record_date < today_wib
            is_today_and_late = (
                record_date == today_wib and 
                (now_wib.hour > target_hour or (now_wib.hour == target_hour and now_wib.minute >= target_minute))
            )

            if is_past_day or is_today_and_late:
                # 🛑 STRONGEST PROTECTION AGAINST DOUBLE STAMP 🛑
                # Double-check the database *right before* insertion.
                # If two workers bypassed the Postgres lock, the first one to commit will save the 'out'.
                # The second worker will hit this query, see the 'out', and skip.
                if dialect.startswith("postgresql"):
                    date_filter = func.date(func.timezone('Asia/Jakarta', models.Attendance.timestamp))
                else:
                    date_filter = func.date(models.Attendance.timestamp)

                existing_out = db.query(models.Attendance.id).filter(
                    models.Attendance.user_id == record.user_id,
                    models.Attendance.attendance_type == "out",
                    date_filter == record_date
                ).first()

                if not existing_out:
                    # Create checkout at the configured time of the check-in day
                    checkout_time = datetime.combine(record_date, datetime.min.time()).replace(tzinfo=WIB_TIMEZONE) + timedelta(hours=target_hour, minutes=target_minute)
                    
                    new_record = models.Attendance(
                        user_id=record.user_id,
                        method="system_auto",
                        attendance_type="out",
                        status="auto",
                        timestamp=checkout_time
                    )
                    db.add(new_record)
                    # Commit immediately per user so other workers see it instantly
                    db.commit()
                    count += 1
                    logger.info(f"Auto check-out created for User {record.user_id} on date {record_date}")

        if count > 0:
            logger.info(f"Auto check-out process complete. {count} users checked out.")
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
            
            # Check if it matches configured time
            if now_wib.hour == settings.AUTO_CHECKOUT_HOUR and now_wib.minute == settings.AUTO_CHECKOUT_MINUTE:
                logger.info(f"Triggering {settings.AUTO_CHECKOUT_HOUR:02d}:{settings.AUTO_CHECKOUT_MINUTE:02d} WIB Auto Check-out...")
                await perform_auto_checkout()
                # Sleep for 61 seconds to ensure we don't trigger twice in the same minute
                await asyncio.sleep(61)
            else:
                # Check every 30 seconds to be precise but not too frequent
                await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
            await asyncio.sleep(60)
