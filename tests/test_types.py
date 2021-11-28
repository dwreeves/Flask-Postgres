import os
import typing as t
import warnings

import pytest

from flask_postgres.exceptions import PostgresUrlNotSet
from flask_postgres.types import PostgresUri


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
        "FLASK_POSTGRES_ADMIN_DBNAME": "johndoe"
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/johndoe"
)

typical_config_w_custom_admin_w_forward_slash = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://foo:bar@hello:12345/world",
        "FLASK_POSTGRES_ADMIN_DBNAME": "/johndoe"
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/johndoe"
)

config_with_env_var = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://foo:bar@hello:12345/world",
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/johndoe",
    env_vars={"FLASK_POSTGRES_ADMIN_DBNAME": "johndoe"}
)

config_with_env_var_that_gets_overruled = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://foo:bar@hello:12345/world",
        "FLASK_POSTGRES_ADMIN_DBNAME": "johndoe"
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/johndoe",
    env_vars={"FLASK_POSTGRES_ADMIN_DBNAME": "overrule_me_please"}
)

config_with_sqla_uri_that_gets_overruled = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://dont:use@me:12345/please",
        "FLASK_POSTGRES_TARGET_DATABASE_URI": "postgresql://foo:bar@hello:12345/world",
        "FLASK_POSTGRES_ADMIN_DBNAME": "johndoe"
    },
    expected_admin_uri="postgresql://foo:bar@hello:12345/johndoe",
)

config_with_env_var_that_overrules_sqla_uri = AdminUriTestConf(
    app_config={
        "SQLALCHEMY_DATABASE_URI": "postgresql://dont:use@me:12345/please",
        "FLASK_POSTGRES_ADMIN_DBNAME": "johndoe"
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
@pytest.mark.filterwarnings("ignore:Please do not put a slash in front")
def test_default_admin_uri(base_app, conf, monkeypatch):
    """This app critically depends on how it resolves config variables. So this
    test doesn't just cover the get_admin_uri function, it also covers all of
    the config resolution logic.
    """
    if conf.env_vars:
        for k, v in conf.env_vars.items():
            monkeypatch.setitem(os.environ, k, v)

    base_app.config.update(conf.app_config)

    with base_app.app_context():
        val = PostgresUri.default().admin_uri()

    assert val == PostgresUri(conf.expected_admin_uri)


def test_get_admin_uri_raises_err_if_no_config(base_app):

    with pytest.raises(PostgresUrlNotSet):
        with base_app.app_context():
            PostgresUri.default().admin_uri()


def test_swap_db_name():
    val = PostgresUri("postgres://foo:bar@hello.world/replace_me") \
        .admin_uri(dbname="replaced_with")

    expected = PostgresUri("postgres://foo:bar@hello.world/replaced_with")

    assert val == expected
