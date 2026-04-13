import logging
import io
import oss2
from app.core.config import settings

logger = logging.getLogger(__name__)

# Strip any scheme prefix so oss2 can build the correct endpoint URL.
def _clean_endpoint(url: str | None) -> str | None:
    if not url:
        return None
    return url.replace("https://", "").replace("http://", "").rstrip("/")


class S3Service:
    def __init__(self):
        self.bucket = None

        if all([settings.S3_ACCESS_KEY_ID, settings.S3_SECRET_ACCESS_KEY, settings.S3_BUCKET]):
            try:
                endpoint = _clean_endpoint(settings.S3_ENDPOINT) or "oss-ap-southeast-1.aliyuncs.com"
                auth = oss2.Auth(settings.S3_ACCESS_KEY_ID, settings.S3_SECRET_ACCESS_KEY)
                self.bucket = oss2.Bucket(auth, f"https://{endpoint}", settings.S3_BUCKET)
                logger.info(f"OSS bucket initialized: {settings.S3_BUCKET} @ {endpoint}")
            except Exception:
                logger.exception("Error initializing Aliyun OSS client")
        else:
            logger.warning("S3 credentials not fully configured. OSS operations will fail.")

    def upload_file(self, file_content: bytes, object_name: str) -> bool:
        """Upload a file to Aliyun OSS bucket."""
        if not self.bucket:
            logger.error("OSS bucket not initialized.")
            return False

        # Ensure object_name is a plain string (PostgreSQL may return memoryview)
        object_name = str(object_name)

        try:
            result = self.bucket.put_object(
                object_name,
                io.BytesIO(file_content),
                headers={'Content-Type': 'image/jpeg'}
            )
            logger.info(f"OSS upload success: {object_name} (status={result.status})")
            return result.status in (200, 201)
        except Exception:
            logger.exception("OSS Upload Error")
            return False

    def download_file(self, object_name: str) -> bytes | None:
        """Download a file from Aliyun OSS bucket."""
        if not self.bucket:
            logger.error("OSS bucket not initialized.")
            return None

        # Ensure object_name is a plain string (PostgreSQL may return memoryview)
        object_name = str(object_name)

        try:
            result = self.bucket.get_object(object_name)
            return result.read()
        except oss2.exceptions.NoSuchKey:
            logger.error(f"OSS key not found: {object_name}")
            return None
        except Exception:
            logger.exception("OSS Download Error")
            return None

    def generate_presigned_url(self, object_name: str, expiration: int = 3600) -> str | None:
        """Generate a presigned URL for an OSS object."""
        if not self.bucket:
            logger.error("OSS bucket not initialized.")
            return None

        # Ensure object_name is a plain string (PostgreSQL may return memoryview)
        object_name = str(object_name)
        try:
            return self.bucket.sign_url('GET', object_name, expiration)
        except Exception:
            logger.exception("OSS Presigned URL Error")
            return None


s3_service = S3Service()
