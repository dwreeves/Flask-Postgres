import sys
import functools
import inspect
import typing as t
from urllib.parse import urlparse as _urlparse
from urllib.parse import urlunparse
from urllib.parse import ParseResult

import click
from flask import Flask
from flask import current_app
from flask import has_app_context
from flask_sqlalchemy import SQLAlchemy

from . import config
from ._compat import psycopg
from .exceptions import SqlaExtensionNotFound
from .exceptions import EnvironmentNotAllowed


@functools.wraps(_urlparse)
def urlparse(uri: str, *args, **kwargs) -> ParseResult:
    """
    Parse database URLs + builtin validation. Better to validate here than to
    stumble into an unpredictable and cryptic error message down the line.
    """
    data = _urlparse(uri, *args, **kwargs)
    assert data.scheme, (
        f"The URI {uri!r} does not have a valid scheme."
    )
    assert data.netloc, (
        f"The URI {uri!r} does not have a valid host."
    )
    assert data.path, (
        f"The URI {uri!r} does not have a valid path/database name."
    )
    return data


@functools.wraps(click.echo)
def echo(*args, **kwargs) -> None:
    """
    Most of our outputs relate to significant changes to the state of a file
    system and/or a database, so we should print to `stderr` by default.
    """
    kwargs.setdefault("file", sys.stderr)
    return click.echo(*args, **kwargs)


def swap_db_name(
        uri: str,
        new_db_name: str
) -> str:
    data = urlparse(uri)._asdict()
    data["path"] = new_db_name
    return urlunparse(ParseResult(**data))


def extract_db_name(uri: str) -> str:
    return urlparse(uri).path.replace("/", "", 1)


def get_admin_uri(
        target_uri: t.Optional[str] = None,
        admin_path: t.Optional[str] = None
) -> str:
    def _parse_admin_path(s: str) -> str:
        if s.startswith("/"):
            s = s[1:]
        return s

    return swap_db_name(
        target_uri or config.get("FLASK_POSTGRES_TARGET_DATABASE_URI"),
        admin_path or _parse_admin_path(config.get("FLASK_POSTGRES_ADMIN_PATH")),
    )


def get_db() -> SQLAlchemy:
    if not has_app_context():
        # RuntimeError is the same err type raised by flask.globals
        raise RuntimeError("The app context is currently not active.")
    if "sqlalchemy" not in current_app.extensions:
        raise SqlaExtensionNotFound
    return current_app.extensions["sqlalchemy"].db


def raise_err_if_disallowed():
    """
    You can protect your app against accidental or (some, but not much)
    malicious use in sensitive environments with the
    `FLASK_POSTGRES_CLI_DISALLOWED_ENVS` config variable.
    """
    li = config.get("FLASK_POSTGRES_CLI_DISALLOWED_ENVS")
    if isinstance(li, str):
        li = li.split(";")
    if current_app.env in li:
        raise EnvironmentNotAllowed


def database_exists(
        database_name: str,
        conn: "psycopg.Connection"
) -> bool:
    cursor = conn.cursor()

    try:
        exists = bool(cursor.execute(
            "SELECT MAX((datname = %s)::int) FROM pg_database;",
            (database_name,)
        ).fetchone()[0])
    finally:
        cursor.close()

    return exists


def resolve_init_db_callback(
        callback: callable
) -> t.Callable[[Flask, SQLAlchemy], t.Any]:

    app_in_params = "app" in inspect.signature(callback).parameters
    db_in_params = "db" in inspect.signature(callback).parameters

    # code is a little wet, but I don't mind avoiding nonlocals and over-the-
    # top abstraction.

    if app_in_params and db_in_params:
        def resolved_callback(app: Flask, db: SQLAlchemy):
            return callback(app=current_app, db=get_db())
    elif app_in_params and not db_in_params:
        def resolved_callback(app: Flask, db: SQLAlchemy):
            return callback(app=current_app)
    elif not app_in_params and db_in_params:
        def resolved_callback(app: Flask, db: SQLAlchemy):
            return callback(db=get_db())
    else:
        def resolved_callback(app: Flask, db: SQLAlchemy):
            return callback()

    return resolved_callback


def echo_error_as_warning(e: Exception) -> None:
    msg = e.args[0]
    if "FATAL:" in msg:  # psycopg2 exceptions
        msg = "FATAL:".join(msg.split("FATAL:")[1:]).strip()
    echo(click.style(msg, fg="yellow"), )
