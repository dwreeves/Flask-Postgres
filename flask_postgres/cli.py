import sys
import contextlib
import typing as t

import click
import sqlalchemy.exc
from flask import current_app
from flask.cli import AppGroup
from flask.cli import ScriptInfo
from flask.cli import with_appcontext

from . import config
from ._compat import check_dependencies
from ._compat import psycopg
from ._compat import errors
from .utils import extract_db_name
from .utils import get_admin_uri
from .utils import get_db
from .utils import echo_error_as_warning
from .utils import echo
from .utils import raise_err_if_disallowed
from .utils import resolve_init_db_callback
from .utils import database_exists

FC = t.TypeVar("FC", t.Callable[..., t.Any], click.Command)


@contextlib.contextmanager
def may_not_exist_context():
    try:
        yield
    except sqlalchemy.exc.OperationalError as e:
        if e.code != "e3q8":
            raise
        echo_error_as_warning(e)
    except errors.lookup("3D000") as e:  # InvalidCatalogName
        echo_error_as_warning(e)


@contextlib.contextmanager
def may_already_exist_context():
    try:
        yield
    except errors.lookup("42P04") as e:  # DuplicateDatabase
        echo_error_as_warning(e)


class ContextMixin(click.Parameter):

    def get_default(
            self,
            ctx: click.Context,
            *args,
            **kwargs
    ) -> t.Optional[t.Any]:
        with ctx.ensure_object(ScriptInfo).load_app().app_context():
            return super().get_default(ctx, *args, **kwargs)


class ContextOption(ContextMixin, click.Option):
    """Option that can load defaults with an active app context."""
    pass


class ContextArgument(ContextMixin, click.Argument):
    """Argument that can load defaults with an active app context."""
    pass


def get_connection(ctx: click.Context, admin_uri: str) -> "psycopg.Connection":
    conn = psycopg.connect(admin_uri)
    conn.autocommit = True
    ctx.call_on_close(conn.close)
    return conn


@click.group("psql", cls=AppGroup)
@with_appcontext
def cli():
    """
    Manage your PostgreSQL database instance.
    """
    check_dependencies()
    raise_err_if_disallowed()


cli: AppGroup


def database_name_option(
        operation_past_tense: str
) -> t.Callable[[FC], FC]:
    return click.option(
        "--database-name", "-d",
        cls=ContextOption,
        default=lambda: extract_db_name(
            config.get("FLASK_POSTGRES_TARGET_DATABASE_URI")),
        show_default=True,
        help=f"The URI of the database to be {operation_past_tense}. By"
             " default, this is derived from the SQLALCHEMY_DATABASE_URI."
    )


admin_uri_option = click.option(
    "--admin-uri", "-u", "admin_uri",
    cls=ContextOption,
    default=get_admin_uri,
    show_default=True,
    help="PostgreSQL database URI to create. By default, this is your"
         " SQLALCHEMY_DATABASE_URI but with 'postgres' as the path."
)


force_delete_option = click.option(
    "--force", "-f",
    cls=ContextOption,
    is_flag=True,
    default=False,
    help="If true, then force delete the database."
)


@cli.command("create")
@database_name_option("created")
@admin_uri_option
@with_appcontext
@click.pass_context
def create_db_command(
        ctx: click.Context,
        database_name: str,
        admin_uri: str,
        **kwargs
):
    """Create the database."""
    conn = get_connection(ctx, admin_uri)
    cursor = conn.cursor()
    try:
        with may_already_exist_context():
            cursor.execute(f"CREATE DATABASE {database_name};")
            echo(f'database "{database_name}" was created')
    finally:
        cursor.close()


create_db_command: click.Command


@cli.command("init")
@with_appcontext
def init_db_command(**kwargs):
    """Init the database."""
    with may_not_exist_context():
        db = get_db()
        if config.registered_callback:
            callback = resolve_init_db_callback(config.registered_callback)
            callback(current_app, db)
        else:
            db.create_all()
        database_name = kwargs.get("database_name") \
            or extract_db_name(str(db.engine.url))
        echo(f'database "{database_name}" was initialized')


init_db_command: click.Command


@cli.command("drop")
@database_name_option("dropped")
@admin_uri_option
@force_delete_option
@with_appcontext
@click.pass_context
def drop_db_command(
        ctx: click.Context,
        database_name: str,
        admin_uri: str,
        force: bool,
        **kwargs
):
    """Delete the database."""
    conn = get_connection(ctx, admin_uri)
    if force is not True:

        if not database_exists(database_name=database_name, conn=conn):
            msg = f'database "{database_name}" does not exist'
            echo(click.style(msg, fg="yellow"))
            return

        # Don't print the prompt to stderr
        # So use click.echo() instead of echo().
        click.echo(
            f'Are you sure you want to delete database "{database_name}"?'
        )
        click.echo(
            "Type in the database name"
            f' "{click.style(database_name, fg="red")}"'
            " to confirm.")
        confirmation = click.prompt("Database name")

        if database_name != confirmation:
            echo(click.style(
                f'The input "{confirmation}" does not match the database name.'
                f' The database "{database_name}" will not be deleted.',
                fg="red"
            ))
            sys.exit(1)

    cursor = conn.cursor()

    try:
        with may_not_exist_context():
            cursor.execute(f"DROP DATABASE {database_name};")
            echo(f'database "{database_name}" was deleted')
    finally:
        cursor.close()


drop_db_command: click.Command


@cli.command("setup")
@database_name_option("setup")
@admin_uri_option
@click.pass_context
@with_appcontext
def setup_db_command(
        ctx: click.Context,
        **kwargs
):
    """Create and init the database."""
    ctx.forward(create_db_command)
    ctx.forward(init_db_command)


setup_db_command: click.Command


@cli.command("reset")
@database_name_option("reset")
@admin_uri_option
@force_delete_option
@click.pass_context
@with_appcontext
def reset_db_command(
        ctx: click.Context,
        **kwargs
):
    """Delete, then create and init the database."""
    ctx.forward(drop_db_command)
    ctx.forward(create_db_command)
    ctx.forward(init_db_command)


reset_db_command: click.Command
