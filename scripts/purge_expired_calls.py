from faultbridge.config import Settings
from faultbridge.services.database import Database


def main() -> None:
    settings = Settings()
    database = Database(settings.database_url)
    try:
        count = database.purge_expired_calls(settings.transcript_retention_days)
        print(f"Purged {count} expired call session(s).")
    finally:
        database.close()


if __name__ == "__main__":
    main()
