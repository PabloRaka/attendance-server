import os
import sys

# Add current dir to path to import app
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models

def fix_null_fullnames():
    db = SessionLocal()
    try:
        # Pydantic validation error was specifically about 'None' (null)
        users_with_null_name = db.query(models.User).filter(models.User.fullname == None).all()
        
        if not users_with_null_name:
            print("Everything looks good! No users found with null fullname.")
            return

        print(f"Found {len(users_with_null_name)} users with null fullname.")
        for user in users_with_null_name:
            # Fallback to username if fullname is missing
            user.fullname = user.username
            print(f"Fixed user: {user.username} (setting fullname to username)")
        
        db.commit()
        print("\nSuccessfully updated all users. The ResponseValidationError should be resolved now.")
    except Exception as e:
        db.rollback()
        print(f"Error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_null_fullnames()
