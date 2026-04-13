import oss2
import os
import sys

# Add current dir to path to import app
sys.path.append(os.getcwd())

from app.core.config import settings

def _clean_endpoint(url: str | None) -> str | None:
    if not url:
        return None
    return url.replace("https://", "").replace("http://", "").rstrip("/")

endpoint = _clean_endpoint(settings.S3_ENDPOINT) or "oss-ap-southeast-1.aliyuncs.com"
auth = oss2.Auth(settings.S3_ACCESS_KEY_ID, settings.S3_SECRET_ACCESS_KEY)
bucket = oss2.Bucket(auth, f"https://{endpoint}", settings.S3_BUCKET)

object_name = "faces/user_10260.jpg" 
exists = bucket.object_exists(object_name)

print(f"Object {object_name} exists: {exists}")
