import os
import inspect
import pytest
import typing as t

from flask_sqlalchemy import SQLAlchemy

from flask_postgres.utils import swap_db_name
from flask_postgres.utils import database_exists
from flask_postgres.utils import resolve_init_db_callback
from flask_postgres.utils import get_db
from flask_postgres.utils import raise_err_if_disallowed
from flask_postgres.utils import get_admin_uri
from flask_postgres.exceptions import SqlaExtensionNotFound
from flask_postgres.exceptions import EnvironmentNotAllowed
from flask_postgres.exceptions import PostgresUrlNotSet


def test_swap_db_name_function():
    res = swap_db_name(
        "postgres://foo@bar:hello.world/replace_me",
        "replaced_with"
    )
    assert res == "postgres://foo@bar:hello.world/replaced_with"


def test_database_exists_function(
        admin_connection,
        db_params
):
    """It's critical that this test passes because other tests use the
    `database_exists` function to run their own tests.
    """
    dbname = db_params.get("dbname")
    assert not database_exists(database_name=dbname, conn=admin_connection)

    cursor = admin_connection.cursor()
    cursor.execute(f"CREATE DATABASE {dbname};")
    assert database_exists(database_name=dbname, conn=admin_connection)

    cursor.execute(f"DROP DATABASE {dbname};")
    assert not database_exists(database_name=dbname, conn=admin_connection)


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
    db1 = SQLAlchemy(base_app)
    with base_app.app_context():
        db2 = get_db()
    assert db1 is db2

    # No app context
    with pytest.raises(RuntimeError):
        get_db()


def test_raise_err_if_disallowed_function(base_app):
    # Nothing should happen
    with base_app.app_context():
        raise_err_if_disallowed()

    base_app.config["FLASK_POSTGRES_CLI_DISALLOWED_ENVS"] = [base_app.env]

    # Now we should see an error
    with pytest.raises(EnvironmentNotAllowed):
        with base_app.app_context():
            raise_err_if_disallowed()


class AdminUriTestConf(t.NamedTuple):
    app_config: t.Dict[str, t.Any]
    expected_admin_uri: str
    env_vars: t.Optional[t.Dict[str, str]] = None


typical_config = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://foo:bar@hello:12345/world"
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/postgres"
)

typical_config_w_custom_admin = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://foo:bar@hello:12345/world",
        "FLASK_POSTGRES_ADMIN_PATH": "johndoe"
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/johndoe"
)

typical_config_w_custom_admin_w_forward_slash = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://foo:bar@hello:12345/world",
        "FLASK_POSTGRES_ADMIN_PATH": "/johndoe"
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/johndoe"
)

config_with_env_var = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://foo:bar@hello:12345/world",
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/johndoe",
    env_vars={"FLASK_POSTGRES_ADMIN_PATH": "johndoe"}
)

config_with_env_var_that_gets_overruled = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://foo:bar@hello:12345/world",
        "FLASK_POSTGRES_ADMIN_PATH": "johndoe"
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/johndoe",
    env_vars={"FLASK_POSTGRES_ADMIN_PATH": "overrule_me_please"}
)

config_with_sqla_uri_that_gets_overruled = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://dont:use@me:12345/please",
        "FLASK_POSTGRES_TARGET_DATABASE_URI": "postgresql://foo:bar@hello:12345/world",
        "FLASK_POSTGRES_ADMIN_PATH": "johndoe"
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/johndoe",
)

config_with_env_var_that_overrules_sqla_uri = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://dont:use@me:12345/please",
        "FLASK_POSTGRES_ADMIN_PATH": "johndoe"
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/johndoe",
    env_vars={
        "FLASK_POSTGRES_TARGET_DATABASE_URI": "postgresql://foo:bar@hello:12345/world"
    }
)


@pytest.mark.parametrize(
    "conf", [
        typical_config,
        typical_config_w_custom_admin,
        typical_config_w_custom_admin_w_forward_slash,
        config_with_env_var,
        config_with_env_var_that_gets_overruled,
        config_with_sqla_uri_that_gets_overruled,
        config_with_env_var_that_overrules_sqla_uri
    ]
)
def test_get_admin_uri_function(base_app, conf, monkeypatch):
    """This app critically depends on how it resolves config variables. So this
    test doesn't just cover the get_admin_uri function, it also covers all of
    the config resolution logic.
    """
    if conf.env_vars:
        for k, v in conf.env_vars.items():
            monkeypatch.setitem(os.environ, k, v)

    base_app.config.update(conf.app_config)

    with base_app.app_context():
        res = get_admin_uri()

    assert res == conf.expected_admin_uri


def test_get_admin_uri_raises_err_if_no_config(base_app):

    with pytest.raises(PostgresUrlNotSet):
        with base_app.app_context():
            get_admin_uri()
