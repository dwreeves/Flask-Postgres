import inspect
import pytest

from flask_sqlalchemy import SQLAlchemy

from flask_postgres.ops import database_exists
from flask_postgres.utils import resolve_init_db_callback
from flask_postgres.utils import get_db
from flask_postgres.utils import raise_err_if_disallowed
from flask_postgres.exceptions import SqlaExtensionNotFound
from flask_postgres.exceptions import EnvironmentNotAllowed

try:
    from importlib import metadata  # type: ignore[import,unused-ignore]
except ImportError:
    # Python < 3.8
    import importlib_metadata as metadata  # type: ignore[no-redef,import-not-found]


def test_database_exists_function(
        admin_connection,
        db_params
):
    """It's critical that this test passes because other tests use the
    `database_exists` function to run their own tests.
    """
    with admin_connection.cursor() as cursor:
        dbname = db_params.get("dbname")
        assert not database_exists(cursor, dbname)

        cursor = admin_connection.cursor()
        cursor.execute(f"CREATE DATABASE {dbname};")
        assert database_exists(cursor, dbname)

        cursor.execute(f"DROP DATABASE {dbname};")
        assert not database_exists(cursor, dbname)


@pytest.mark.parametrize(
    ["func", "app_is_arg", "db_is_arg"], [
        (lambda: print("I ran OK"), False, False),
        (lambda app: print("I ran OK"), True, False),
        (lambda db: print("I ran OK"), False, True),
        (lambda app, db: print("I ran OK"), True, True),
        (lambda db, app: print("I ran OK"), True, True),
    ])
@pytest.mark.filterwarnings("ignore:.*SQLALCHEMY.*")
def test_resolve_init_db_callback_function(
    base_app,
    func: callable,
    app_is_arg: bool,
    db_is_arg: bool,
capsys
):
    assert app_is_arg == bool("app" in inspect.signature(func).parameters)
    assert db_is_arg == bool("db" in inspect.signature(func).parameters)

    new_func = resolve_init_db_callback(func)

    assert "app" in inspect.signature(new_func).parameters
    assert "db" in inspect.signature(new_func).parameters

    base_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db/"
    db = SQLAlchemy(base_app)

    assert capsys.readouterr().out == ""

    with base_app.app_context():
        new_func(app=base_app, db=db)  # noqa

    assert capsys.readouterr().out == "I ran OK\n"


@pytest.mark.filterwarnings("ignore:.*SQLALCHEMY.*")
def test_get_db_function(base_app):
    # No db extension
    with pytest.raises(SqlaExtensionNotFound):
        with base_app.app_context():
            get_db()

    # This works perfectly fine.
    base_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db/"
    db1 = SQLAlchemy(base_app)
    with base_app.app_context():
        db2 = get_db()
    assert db1 is db2

    # No app context
    with pytest.raises(RuntimeError):
        get_db()


major, minor, *_ = metadata.version("flask").split(".")

# ≤ 2.2 only
@pytest.mark.skipif(
    condition=not (3 > int(major) >= 2 and 3 > int(minor) >= 0),
    reason="app.env is deprecated in Flask 2.3.0+"
)
def test_raise_err_if_disallowed_function(base_app):
    # Nothing should happen
    with base_app.app_context():
        raise_err_if_disallowed()

    base_app.config["FLASK_POSTGRES_CLI_DISALLOWED_ENVS"] = [base_app.env]

    # Now we should see an error
    with pytest.raises(EnvironmentNotAllowed):
        with base_app.app_context():
            raise_err_if_disallowed()
