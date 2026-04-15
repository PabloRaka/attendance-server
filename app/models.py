from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean, LargeBinary
from sqlalchemy.sql import func
import enum
from .database import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"

class AttendanceType(str, enum.Enum):
    IN = "in"
    OUT = "out"

from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    fullname = Column(String)
    hashed_password = Column(String)
    role = Column(String, default=UserRole.USER)
    face_image = Column(LargeBinary, nullable=True)  # Stored face binary data
    face_embedding = Column(LargeBinary, nullable=True) # Stored 128-float vector binary

    # Relationships
    attendances = relationship("Attendance", back_populates="user", cascade="all, delete-orphan")

    @property
    def has_face(self) -> bool:
        return self.face_image is not None



class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    method = Column(String) # 'face' or 'qr'
    attendance_type = Column(String) # 'in' or 'out'
    status = Column(String, nullable=True) # 'terlambat' or 'tepat waktu'
    latitude = Column(String, nullable=True)
    longitude = Column(String, nullable=True)
    location_name = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="attendances")

class QRChallenge(Base):
    __tablename__ = "qr_challenges"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
