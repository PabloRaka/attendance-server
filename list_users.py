import os
import sys

# Add current dir to path to import app
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models

db = SessionLocal()
try:
    users = db.query(models.User).limit(10).all()
    print("Listing first 10 users in DB:")
    for u in users:
        print(f" - ID: {u.id}, Username: {u.username}, Fullname: {u.fullname}, Face: {u.face_image}")
finally:
    db.close()
