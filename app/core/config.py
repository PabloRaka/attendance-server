import os
from urllib.parse import quote_plus
from typing import ClassVar

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

# Base directory of the backend project (root of the backend folder)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure .env is loaded from the root directory regardless of CWD
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Settings(BaseSettings):
    """Application configuration, including database connection handling."""

    # Direct SQLAlchemy URL (takes precedence when provided)
    DATABASE_URL: str | None = os.getenv("DATABASE_URL")

    # Dialect-specific pieces used to construct the URL when DATABASE_URL is empty
    DATABASE_DIALECT: str = os.getenv("DATABASE_DIALECT", "sqlite").lower()
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str | None = os.getenv("DB_PORT")
    DB_USER: str | None = os.getenv("DB_USER")
    DB_PASSWORD: str | None = os.getenv("DB_PASSWORD")
    DB_NAME: str | None = os.getenv("DB_NAME")
    # Path is only used when DATABASE_DIALECT resolves to sqlite.
    # We resolve it to be absolute relative to the project root for consistency.
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "attendance.db")

    @field_validator("SQLITE_PATH", mode="before")
    @classmethod
    def assemble_sqlite_path(cls, v: str | None) -> str:
        """Ensure SQLITE_PATH is always absolute relative to BASE_DIR."""
        if not v:
            v = "attendance.db"
        if os.path.isabs(v):
            return v
        return os.path.abspath(os.path.join(BASE_DIR, v))


    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-for-development")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440)
    )

    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")
    
    @property
    def allowed_origins_list(self) -> list[str]:
        """Convert comma-separated string to list of origins."""
        return [
            origin.strip() 
            for origin in self.ALLOWED_ORIGINS.split(",") 
            if origin.strip()
        ]
    
    FACE_SIMILARITY_THRESHOLD: float = float(
        os.getenv("FACE_SIMILARITY_THRESHOLD", "0.60")
    )

    # S3 Configuration
    S3_ACCESS_KEY_ID: str | None = os.getenv("S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY: str | None = os.getenv("S3_SECRET_ACCESS_KEY")
    S3_REGION: str = os.getenv("S3_DEFAULT_REGION", "ap-southeast-1")
    S3_BUCKET: str | None = os.getenv("S3_BUCKET")
    S3_ENDPOINT: str | None = os.getenv("S3_ENDPOINT")
    S3_USE_PATH_STYLE_ENDPOINT: bool = os.getenv("S3_USE_PATH_STYLE_ENDPOINT", "false").lower() == "true"
    S3_CDN_ENDPOINT: str | None = os.getenv("S3_CDN_ENDPOINT")

    # External User Management API
    USER_MANAGEMENT_API_URL: str = os.getenv("USER_MANAGEMENT_API_URL", "https://newapidevkiismanajemenuser.ibik.ac.id").rstrip("/")


    DIALECT_DRIVER_MAP: ClassVar[dict[str, str]] = {
        "postgres": "postgresql+psycopg2",
        "postgresql": "postgresql+psycopg2",
        "mysql": "mysql+pymysql",
    }

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:  # noqa: N802 (library expects upper case)
        """Return a ready-to-use SQLAlchemy connection string.

        Supports PostgreSQL and MySQL, with SQLite as the default fallback.
        """

        if self.DATABASE_URL:
            return self.DATABASE_URL

        dialect = self.DIALECT_DRIVER_MAP.get(self.DATABASE_DIALECT, self.DATABASE_DIALECT)

        if dialect.startswith("sqlite"):
            # Allow users to pass a fully-qualified sqlite URL via SQLITE_PATH
            if self.SQLITE_PATH.startswith("sqlite"):
                return self.SQLITE_PATH
            return f"sqlite:///{self.SQLITE_PATH}"

        auth_segment = ""
        if self.DB_USER:
            auth_segment = quote_plus(self.DB_USER)
            if self.DB_PASSWORD:
                auth_segment += f":{quote_plus(self.DB_PASSWORD)}"
            auth_segment += "@"

        port_segment = f":{self.DB_PORT}" if self.DB_PORT else ""
        database = self.DB_NAME or ""

        return f"{dialect}://{auth_segment}{self.DB_HOST}{port_segment}/{database}"


settings = Settings()
