import sys
import functools
import inspect
import typing as t

import click
from flask import Flask
from flask import current_app
from flask import has_app_context
from flask_sqlalchemy import SQLAlchemy

from flask_postgres import config
from flask_postgres.exceptions import SqlaExtensionNotFound
from flask_postgres.exceptions import EnvironmentNotAllowed


@functools.wraps(click.echo)
def echo(*args, **kwargs) -> None:
    """
    Most of our outputs relate to significant changes to the state of a file
    system and/or a database, so we should print to `stderr` by default.
    """
    kwargs.setdefault("file", sys.stderr)
    return click.echo(*args, **kwargs)


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

    This is only enabled for the CLI.
    """
    li = config.get("FLASK_POSTGRES_CLI_DISALLOWED_ENVS")
    if isinstance(li, str):
        li = li.split(";")
    if current_app.env in li:
        raise EnvironmentNotAllowed


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
