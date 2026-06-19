import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Settings:
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    # API Security Key
    API_KEY: str = os.getenv("API_KEY", "")
    
    # Database Settings
    DATABASE_TYPE: str = os.getenv("DATABASE_TYPE", "sqlite").lower()
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "trades.db")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Google Sheets Settings
    GOOGLE_SPREADSHEET_ID: str = os.getenv("GOOGLE_SPREADSHEET_ID", "")
    # This can be a filename (e.g. service_account.json) or a raw JSON string
    GOOGLE_SERVICE_ACCOUNT_CREDENTIALS: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS", "")
    
    # Discord Integration
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")
    DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
    DISCORD_CHANNEL_ID: int = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

    def validate(self):
        """Validate critical configuration combinations."""
        if self.DATABASE_TYPE == "postgres" and not self.DATABASE_URL:
            raise ValueError("DATABASE_TYPE is 'postgres' but DATABASE_URL is not set.")
        if self.DATABASE_TYPE == "sheets" and not self.GOOGLE_SPREADSHEET_ID:
            raise ValueError("DATABASE_TYPE is 'sheets' but GOOGLE_SPREADSHEET_ID is not set.")
        if self.DATABASE_TYPE not in ["sqlite", "postgres", "sheets"]:
            raise ValueError(f"Unsupported DATABASE_TYPE: {self.DATABASE_TYPE}. Must be sqlite, postgres, or sheets.")

settings = Settings()
# Basic validation on startup
try:
    settings.validate()
except Exception as e:
    print(f"Configuration Warning: {e}")
