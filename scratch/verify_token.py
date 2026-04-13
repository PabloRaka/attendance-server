import sys
import os
from datetime import datetime, timedelta
from jose import jwt

# Load secret from .env manually for testing
secret = "HIIk3xySUiBepOQYKKlrTDatekLXzFSIAy94ghutmJmSZ5QFGeaeKGLbVSWANCyk"
algorithm = "HS256"

def create_test_token(username):
    payload = {
        "sub": username,
        "name": "Test User External",
        "role": "user",
        "exp": datetime.utcnow() + timedelta(minutes=15)
    }
    return jwt.encode(payload, secret, algorithm=algorithm)

def verify_token(token):
    try:
        decoded = jwt.decode(token, secret, algorithms=[algorithm])
        print(f"Decoded: {decoded}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    token = create_test_token("testuser123")
    print(f"Token: {token}")
    success = verify_token(token)
    if success:
        print("Verification successful!")
    else:
        sys.exit(1)
