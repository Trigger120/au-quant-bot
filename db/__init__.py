from config import settings
from db.base import AbstractDataStore

def get_db() -> AbstractDataStore:
    """
    Database Factory to retrieve the configured AbstractDataStore instance.
    Automatically connects before returning.
    """
    db_type = settings.DATABASE_TYPE
    
    if db_type == "sqlite":
        from db.sqlite import SQLiteDataStore
        db = SQLiteDataStore(settings.SQLITE_DB_PATH)
    elif db_type == "postgres":
        from db.postgres import PostgresDataStore
        db = PostgresDataStore(settings.DATABASE_URL)
    elif db_type == "sheets":
        from db.sheets import GoogleSheetsDataStore
        db = GoogleSheetsDataStore(
            settings.GOOGLE_SPREADSHEET_ID,
            settings.GOOGLE_SERVICE_ACCOUNT_CREDENTIALS
        )
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
        
    db.connect()
    return db
