import sys
import os
from sqlalchemy.orm import Session

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app import models, database
from app.database import engine
from app.utils.auth import get_password_hash

def create_admin(username, password, fullname):
    # Ensure tables exist
    print(f"Using database at: {engine.url}")
    models.Base.metadata.create_all(bind=engine)
    db: Session = next(database.get_db())
    
    # Check if exists
    existing = db.query(models.User).filter(models.User.username == username).first()
    if existing:
        print(f"User {username} already exists. Updating to Admin.")
        existing.role = "admin"
        existing.hashed_password = get_password_hash(password)
    else:
        new_user = models.User(
            username=username,
            fullname=fullname,
            hashed_password=get_password_hash(password),
            role="admin"
        )
        db.add(new_user)
    
    db.commit()
    print(f"Admin user '{username}' created/updated successfully!")

import getpass

if __name__ == "__main__":
    if len(sys.argv) == 4:
        username = sys.argv[1]
        password = sys.argv[2]
        fullname = sys.argv[3]
    else:
        print("\n--- Create/Update Admin User ---")
        print("Tip: You can also use: python3 create_admin.py <username> <password> <fullname>")
        username = input("Enter Admin Username: ").strip()
        password = getpass.getpass("Enter Admin Password: ")
        fullname = input("Enter Admin Full Name: ").strip()
    
    if not username or not password or not fullname:
        print("\n[Error] All fields are required. Operation cancelled.")
    else:
        create_admin(username, password, fullname)
