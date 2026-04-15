from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    username: str
    fullname: str
    role: str = "user"

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    fullname: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None

class User(UserBase):
    id: int
    has_face: Optional[bool] = None
    has_seen_tutorial: bool = False

    class Config:
        from_attributes = True


class TutorialStatusUpdate(BaseModel):
    has_seen_tutorial: bool


class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
