import os
import sys

# Add current dir to path to import app
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models

db = SessionLocal()
try:
    # Find user by username. User logs show username: 3320250903
    user = db.query(models.User).filter(models.User.username == "3320250903").first()
    if user:
        print(f"Found user in DB: {user.username} (DB PK ID: {user.id})")
        print(f"Old face_image path: {user.face_image}")
        user.face_image = None
        db.commit()
        print("face_image has been reset to None. User can now upload a fresh photo correctly.")
    else:
        print("User with ID 10260 not found.")
finally:
    db.close()
