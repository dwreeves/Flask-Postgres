import pytest
import os
from pytest_postgresql.janitor import DatabaseJanitor
import sqlalchemy as sa

from flask import Flask
from flask_postgres._compat import psycopg  # noqa
from flask_postgres.cli.main import cli


@pytest.fixture
def uri() -> str:
    return os.environ.get(
        "TEST_DATABASE_URI",
        "postgresql://localhost:5432/flask_postgres_test_database"
    )


@pytest.fixture
def db_params(uri) -> dict:
    data = sa.engine.url.make_url(uri).translate_connect_args()
    data.setdefault("dbname", data.pop("database", "localhost"))
    data.setdefault("user", data.pop("username", None))
    data.setdefault("host", data.pop("host", 5432))
    return data


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delitem(os.environ, "FLASK_POSTGRES_TARGET_DATABASE_URI", raising=False)
    monkeypatch.delitem(os.environ, "FLASK_POSTGRES_ADMIN_DBNAME", raising=False)
    monkeypatch.delitem(os.environ, "SQLALCHEMY_DATABASE_URI", raising=False)
    monkeypatch.delitem(os.environ, "FLASK_POSTGRES_CLI_DISALLOWED_ENVS", raising=False)
    yield


@pytest.fixture
def base_app() -> Flask:
    app = Flask("test")
    app.config["ENV"] = "testing"
    app.config["TESTING"] = True
    app.config["DEBUG"] = True
    app.cli.add_command(cli)
    return app


@pytest.fixture(autouse=True)
def admin_connection(db_params) -> "psycopg.Connection":
    admin_params = db_params.copy()
    admin_params["dbname"] = "postgres"
    conn = psycopg.connect(**admin_params)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def uninitialized_database_janitor(db_params: dict):
    """Set up an environment in which the database specified in db_params is
    always cleaned up, even if it wasn't created.

    Creating the database is handled either by other fixtures, or test cases
    themselves.
    """
    janitor = DatabaseJanitor(**db_params, version=9.6)
    yield janitor

    try:
        # Always attempt to drop the database!
        janitor.drop()
    # except psycopg.errors.InvalidCatalogName:
    except psycopg.errors.lookup("3D000"):
        pass


@pytest.fixture
def activated_database(
        db_params: dict,
        uninitialized_database_janitor: DatabaseJanitor
):
    """Initializes the `uninitialized_database_janitor` object.

    We do not return a psycopg.connect() to it because that makes it impossible
    to delete, and some of our tests need to cover the deletion case.
    """
    uninitialized_database_janitor.init()
    yield
