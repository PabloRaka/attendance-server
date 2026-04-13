import logging
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from app.core.config import settings

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = None
        if all([settings.S3_ACCESS_KEY_ID, settings.S3_SECRET_ACCESS_KEY, settings.S3_BUCKET]):
            try:
                # Configure addressing style. Aliyun OSS requires 'virtual' hosted style.
                # Boto3 often defaults to 'path' when a custom endpoint_url is used.
                # Additionally, disable payload signing (chunked encoding) for Aliyun OSS compatibility.
                addressing_style = 'path' if settings.S3_USE_PATH_STYLE_ENDPOINT else 'virtual'
                config = Config(
                    s3={'addressing_style': addressing_style, 'payload_signing_enabled': False},
                    signature_version='s3v4'
                )
                
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                    region_name=settings.S3_REGION,
                    endpoint_url=settings.S3_ENDPOINT,
                    config=config
                )
            except Exception:
                logger.exception("Error initializing S3 client")
        else:
            logger.warning("S3 credentials not fully configured. S3 operations will fail.")

    def upload_file(self, file_content: bytes, object_name: str) -> bool:
        """Upload a file to an S3 bucket."""
        if not self.s3_client:
            logger.error("S3 client not initialized.")
            return False

        try:
            self.s3_client.put_object(
                Bucket=settings.S3_BUCKET,
                Key=object_name,
                Body=file_content,
                ContentType='image/jpeg'
            )
            return True
        except Exception:
            logger.exception("S3 Upload Unexpected Error")
            return False

    def download_file(self, object_name: str) -> bytes | None:
        """Download a file from an S3 bucket."""
        if not self.s3_client:
            logger.error("S3 client not initialized.")
            return None

        try:
            response = self.s3_client.get_object(Bucket=settings.S3_BUCKET, Key=object_name)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"S3 Download Error: {e}")
            return None

    def generate_presigned_url(self, object_name: str, expiration: int = 3600) -> str | None:
        """Generate a presigned URL to share an S3 object."""
        if not self.s3_client:
            logger.error("S3 client not initialized.")
            return None

        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.S3_BUCKET, 'Key': object_name},
                ExpiresIn=expiration
            )
            
            # If CDN is provided, we might need to handle it. 
            # Note: Presigned URLs are host-specific. Simple string replacement might break signature.
            # We'll return the signed URL as-is unless explicitly asked to handle CDN signing.
            if settings.S3_CDN_ENDPOINT:
                # If the user wants to use CDN, they usually have a configuration for it.
                # For now, we return the standard presigned URL.
                pass
                
            return url
        except ClientError as e:
            logger.error(f"S3 Presigned URL Error: {e}")
            return None

s3_service = S3Service()
