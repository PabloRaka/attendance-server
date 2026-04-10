import os
import shutil
import cv2
import numpy as np
import asyncio
from datetime import datetime, date
from sqlalchemy import func as sql_func
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pyzbar.pyzbar import decode
import logging
import secrets
from datetime import datetime, date, timedelta, timezone

from . import models, database
from .database import engine, get_db
from .core.config import settings
from .utils.auth import get_password_hash, verify_password, create_access_token
from .api.deps import get_current_user, get_admin_user
from .schemas.user import UserCreate, User as UserSchema, Token
from .services import face_service
from .api.api_v1 import auth, attendance, users, admin

app = FastAPI(title="Modern Attendance System")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# Include Routers
app.include_router(auth.router)
app.include_router(attendance.router)
app.include_router(users.router)
app.include_router(admin.router)

@app.get("/")
async def root():
    return {"message": "Modern Attendance System API is running"}
