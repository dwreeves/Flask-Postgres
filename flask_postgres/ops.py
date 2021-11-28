"""
Postgresql operations.
"""
import sys
import typing as t
import contextlib

import sqlalchemy.exc
import click

from flask_postgres._compat import psycopg
from flask_postgres._compat import errors
from flask_postgres.utils import echo
from flask_postgres.utils import echo_error_as_warning
from flask_postgres.exceptions import CommandLineModeNotActive


@contextlib.contextmanager
def may_not_exist_context(success_message: t.Optional[str] = None):
    try:
        yield
    except sqlalchemy.exc.OperationalError as e:
        if e.code != "e3q8":
            raise
        echo_error_as_warning(e)
    except errors.lookup("3D000") as e:  # InvalidCatalogName
        echo_error_as_warning(e)
    else:
        if success_message:
            echo(success_message)


@contextlib.contextmanager
def may_already_exist_context(success_message: t.Optional[str] = None):
    try:
        yield
    except errors.lookup("42P04") as e:  # DuplicateDatabase
        echo_error_as_warning(e)
    else:
        if success_message:
            echo(success_message)


def _force_disconnect(cursor, dbname: str) -> None:
    cursor.execute(
        "SELECT pg_terminate_backend(pg_stat_activity.pid)"
        " FROM pg_stat_activity"
        " WHERE pg_stat_activity.datname = %s;",
        (dbname,),
    )


def database_exists(
        cursor,
        dbname: str,
) -> bool:
    cursor.execute(
        "SELECT EXISTS ("
        "SELECT datname"
        " FROM pg_catalog.pg_database"
        " WHERE datname = %s"
        ");",
        (dbname,)
    )
    exists = bool(cursor.fetchone()[0])
    return exists


def create_db(
        *,
        conn: "psycopg.Connection" = None,
        dbname: str,
        command_line_mode: bool = False,
        template: t.Optional[str] = None
) -> None:
    if command_line_mode:
        cm = may_already_exist_context(
            success_message=f'database "{dbname}" was created'
        )
    else:
        cm = contextlib.nullcontext()

    cursor = conn.cursor()
    try:
        with cm:
            if database_exists(cursor=cursor, dbname=dbname):
                raise errors.lookup("42P04")(
                    f'database "{dbname}" already exists')

            if template:
                cursor.execute(f"CREATE DATABASE {dbname} TEMPLATE {template};")
            else:
                cursor.execute(f"CREATE DATABASE {dbname};")
    finally:
        cursor.close()


def drop_db(
        *,
        conn: "psycopg.Connection" = None,
        dbname: str,
        command_line_mode: bool = False,
        force_disconnect: bool = False,
        confirm: bool = False
) -> None:
    if command_line_mode:
        cm = may_not_exist_context(
            success_message=f'database "{dbname}" was deleted'
        )
    else:
        cm = contextlib.nullcontext()

    cursor = conn.cursor()
    try:
        with cm:
            if not database_exists(cursor=cursor, dbname=dbname):
                raise errors.lookup("3D000")(
                    f'database "{dbname}" does not exist')

            if not command_line_mode and confirm:
                raise CommandLineModeNotActive(
                    value=confirm,
                    param="confirm"
                )

            if command_line_mode and confirm:
                click.echo(
                    'Are you sure you want to delete database'
                    f' "{dbname}"?'
                )
                click.echo(
                    "Type in the database name"
                    f' "{click.style(dbname, fg="red")}"'
                    " to confirm.")
                confirmation = click.prompt("Database name")

                if dbname != confirmation:
                    echo(click.style(
                        f'The input "{confirmation}" does not match the'
                        f' database name. The database "{dbname}" will not be'
                        ' deleted.',
                        fg="red"
                    ))
                    sys.exit(1)

            if force_disconnect:
                _force_disconnect(cursor=cursor, dbname=dbname)

            cursor.execute(f"DROP DATABASE {dbname};")

    finally:
        cursor.close()
