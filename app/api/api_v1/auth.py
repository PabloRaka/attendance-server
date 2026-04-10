from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.utils.auth import get_password_hash, verify_password, create_access_token
from app.schemas.user import UserCreate, User as UserSchema, Token
from app.services import face_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=UserSchema)
async def register_user(
    username: str = Form(...),
    password: str = Form(...),
    fullname: str = Form(...),
    role: str = Form("user"),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Check if user exists
    existing_user = db.query(models.User).filter(models.User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    new_user = models.User(
        username=username,
        fullname=fullname,
        hashed_password=get_password_hash(password),
        role=role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # If a face photo was provided during registration, process and save it directly in the DB
    if file and file.filename:
        contents = await file.read()
        face_binary = await face_service.process_and_crop_binary(contents)
        if face_binary:
            new_user.face_image = face_binary
            db.commit()
            db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}
