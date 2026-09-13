from __future__ import annotations

import os
from urllib.parse import urlparse, urlunparse

import psycopg
from psycopg import sql


def main() -> None:
    evaluation_url = os.environ.get("EVALUATION_DATABASE_URL", "")
    runtime_url = os.environ.get("DATABASE_URL", "")
    if not evaluation_url and runtime_url:
        runtime = urlparse(runtime_url)
        runtime_name = runtime.path.strip("/")
        evaluation_url = urlunparse(runtime._replace(path=f"/{runtime_name}_eval"))
    if not evaluation_url:
        raise ValueError("EVALUATION_DATABASE_URL is required")
    parsed = urlparse(evaluation_url)
    database_name = parsed.path.strip("/")
    if not database_name or not any(
        marker in database_name.casefold() for marker in ("eval", "test")
    ):
        raise ValueError("evaluation database name must contain 'eval' or 'test'")
    if evaluation_url == runtime_url:
        raise ValueError("EVALUATION_DATABASE_URL must differ from DATABASE_URL")
    admin_url = urlunparse(parsed._replace(path="/postgres"))
    with psycopg.connect(admin_url, autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
        ).fetchone()
        if not exists:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
            )
            print(f"Created evaluation database {database_name}")
        else:
            print(f"Evaluation database {database_name} already exists")


if __name__ == "__main__":
    main()
