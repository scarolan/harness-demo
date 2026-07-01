import os


class Settings:
    APP_NAME: str = "Harness Demo App"
    DEPLOY_STRATEGY: str = "canary"
    VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    ENVIRONMENT: str = os.getenv("APP_ENVIRONMENT", "local")
    COMMIT_SHA: str = os.getenv("COMMIT_SHA", "unknown")
    BUILD_TIME: str = os.getenv("BUILD_TIME", "unknown")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "users.db")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))


settings = Settings()
