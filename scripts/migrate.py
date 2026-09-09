import os
from pathlib import Path

from faultbridge.services.database import apply_migrations


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    applied = apply_migrations(database_url, Path("migrations"))
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    else:
        print("Database is up to date")


if __name__ == "__main__":
    main()
