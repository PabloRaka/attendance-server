import httpx
import logging
from app.core.config import settings
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class ExternalAuthService:
    def __init__(self):
        self.base_url = settings.USER_MANAGEMENT_API_URL
        logger.info(f"ExternalAuthService initialized with base_url: '{self.base_url}'")

    async def authenticate_external(self, username, password):
        """
        Proxies login request to the external IBIK User Management API.
        Expected endpoint: auth/login
        """
        # Ensure we don't have double slashes
        base = self.base_url.rstrip("/")
        full_url = f"{base}/auth/login"
        
        headers = {
            "Authorization": f"Bearer {settings.SECRET_KEY}",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient(verify=False) as client: # Added verify=False in case of SSL issues on dev
            try:
                logger.info(f"Attempting external auth for {username} at {full_url}")
                response = await client.post(
                    full_url,
                    json={
                        "username": username,
                        "password": password
                    },
                    headers=headers,
                    timeout=15.0,
                    follow_redirects=True
                )
                
                logger.info(f"External API Status: {response.status_code} URL: {response.url}")

                
                if response.status_code == 200:
                    try:
                        return response.json()
                    except Exception as e:
                        logger.error(f"Failed to parse JSON response: {response.text}")
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="External API returned invalid JSON"
                        )
                elif response.status_code == 401:
                    logger.warning(f"External auth failed for user: {username}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid username or password (External API)"
                    )
                else:
                    logger.error(f"External API error: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"External API error: {response.status_code}"
                    )
            except HTTPException:
                # Re-raise HTTPExceptions as-is
                raise
            except httpx.RequestError as e:
                logger.error(f"HTTPExt request error: {type(e).__name__}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"User management service unavailable: {type(e).__name__}"
                )
            except Exception as e:
                logger.error(f"Unexpected error in ExternalAuthService: {type(e).__name__}: {e}", exc_info=True)
                # For debugging, we return the error name
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"External Auth Error ({type(e).__name__}): {str(e)}"
                )


external_auth_service = ExternalAuthService()
